import json
import os
import tempfile
import unittest

from cogram_goai.aliases import expand_tokens
from cogram_goai.notes import Note, NoteStore
from cogram_goai.pipeline import approve_always, run_pipeline
from cogram_goai.skill import (
    GATE_SKILL_NAME,
    PATH_SKILL_NAME,
    REDACT_SKILL_NAME,
    SKILL_CATALOG,
    approval_gate,
    path_guard,
    redact,
)
from cogram_goai.trace import Trace, TraceError


class HashChainTest(unittest.TestCase):
    def test_chain_verifies_after_a_real_run(self):
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "run.jsonl")
        store = NoteStore([
            Note(id="n1", text="retry wrapper reuses a stream on upload", tags=["upload", "retry"]),
        ])
        issue = "Large uploads crash with a timeout on retry; we need a regression test."
        dry = run_pipeline(issue, store, trace=Trace(path=path))
        evidence = {task.id: "ok %s" % task.id for task in dry.subtasks}
        run_pipeline(issue, store, evidence=evidence, approve=approve_always, trace=Trace(path=path))
        loaded = Trace.load(path, verify_chain=True)
        self.assertGreaterEqual(len(loaded.events), 2)
        self.assertEqual(loaded.verify(), [])

    def test_edited_payload_is_detected(self):
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "run.jsonl")
        trace = Trace(path=path)
        trace.record("pipeline", "task_input", chars=4)
        with open(path, "r", encoding="utf-8") as handle:
            entry = json.loads(handle.readline())
        entry["payload"]["chars"] = 99
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")
        loaded = Trace.load(path)
        self.assertTrue(any("hash mismatch" in err for err in loaded.verify()))
        with self.assertRaises(TraceError):
            Trace.load(path, verify_chain=True)


class ConflictTest(unittest.TestCase):
    def test_two_high_causes_suppress_auto_inject(self):
        store = NoteStore([
            Note(
                id="a",
                text="upload timeout from a reused stream",
                tags=["upload", "timeout"],
                cause="reused stream",
                fix="rewind",
            ),
            Note(
                id="b",
                text="upload timeout from a 30s proxy",
                tags=["upload", "timeout"],
                cause="proxy idle timeout",
                fix="raise idle timeout",
            ),
        ])
        result = run_pipeline("upload timeout on retry", store)
        self.assertIsNotNone(result.context["conflict"])
        self.assertEqual(result.context["auto_inject"], [])
        self.assertEqual(len(result.context["conflict"]["causes"]), 2)

    def test_same_cause_does_not_conflict(self):
        store = NoteStore([
            Note(id="a", text="upload timeout stream", tags=["upload"], cause="reused stream"),
            Note(id="b", text="upload timeout rewind", tags=["upload"], cause="reused stream"),
        ])
        result = run_pipeline("upload timeout", store)
        self.assertIsNone(result.context["conflict"])
        self.assertEqual(result.context["auto_inject"], ["a", "b"])

    def test_conflict_does_not_copy_a_side_into_the_capture(self):
        store = NoteStore([
            Note(id="a", text="upload timeout stream", tags=["upload", "retry"], cause="reused stream", fix="rewind"),
            Note(id="b", text="upload timeout proxy", tags=["upload", "retry"], cause="proxy idle", fix="raise"),
        ])
        issue = "Large uploads crash with a timeout on retry; we need a regression test."
        dry = run_pipeline(issue, store)
        evidence = {task.id: "ok %s" % task.id for task in dry.subtasks}
        result = run_pipeline(issue, store, evidence=evidence, approve=approve_always)
        captured = next(note for note in store if note.id == result.captured_note_id)
        self.assertEqual(captured.cause, "")
        self.assertEqual(captured.fix, "")


class SecuritySkillTest(unittest.TestCase):
    def test_redact_strips_token_shapes(self):
        cleaned = redact("set token=ghp_abcdefghijklmnopqrstuvwxyz012345 and password=hunter2")
        self.assertEqual(cleaned["skill"], REDACT_SKILL_NAME)
        self.assertGreaterEqual(cleaned["redactions"], 1)
        self.assertNotIn("hunter2", cleaned["text"])
        self.assertNotIn("ghp_", cleaned["text"])
        self.assertIn("[REDACTED]", cleaned["text"])

    def test_capture_redacts_before_write(self):
        store = NoteStore([
            Note(id="n1", text="retry wrapper reuses a stream on upload", tags=["upload", "retry"]),
        ])
        issue = "Large uploads crash with a timeout on retry; password=supersecret we need a regression test."
        dry = run_pipeline(issue, store)
        evidence = {task.id: "ok %s" % task.id for task in dry.subtasks}
        result = run_pipeline(issue, store, evidence=evidence, approve=approve_always)
        captured = next(note for note in store if note.id == result.captured_note_id)
        self.assertNotIn("supersecret", captured.text)
        self.assertIn("[REDACTED]", captured.text)

    def test_approval_gate_states(self):
        self.assertEqual(approval_gate(False, True)["state"], "blocked_unverified")
        self.assertEqual(approval_gate(True, None)["state"], "pending")
        self.assertTrue(approval_gate(True, True)["allowed"])
        self.assertEqual(approval_gate(True, False)["skill"], GATE_SKILL_NAME)
        self.assertFalse(approval_gate(True, False)["allowed"])

    def test_path_guard_refuses_env_files(self):
        blocked = path_guard("/tmp/.env")
        self.assertEqual(blocked["skill"], PATH_SKILL_NAME)
        self.assertFalse(blocked["allowed"])
        self.assertTrue(path_guard("/tmp/notes.json")["allowed"])

    def test_catalog_lists_five_skills(self):
        names = [item["name"] for item in SKILL_CATALOG]
        self.assertEqual(len(names), 5)
        self.assertIn(REDACT_SKILL_NAME, names)
        self.assertIn(GATE_SKILL_NAME, names)
        self.assertIn(PATH_SKILL_NAME, names)


class ExtraAliasTest(unittest.TestCase):
    def test_cors_and_oauth_expand(self):
        self.assertIn("cors", expand_tokens(["corserror"]))
        self.assertIn("oauth", expand_tokens(["oidc"]))


if __name__ == "__main__":
    unittest.main()
