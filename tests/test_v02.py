import os
import tempfile
import unittest

from cogram_goai.aliases import expand_tokens
from cogram_goai.notes import Note, NoteStore
from cogram_goai.pipeline import approve_always, rollback_capture, run_pipeline
from cogram_goai.skill import BIND_SKILL_NAME, evidence_bind, keyword_recall
from cogram_goai.trace import Trace


class AliasAndBandTest(unittest.TestCase):
    def test_timeout_matches_chinese_synonym(self):
        notes = [Note(id="n1", text="the retry wrapper hits a timeout", tags=["retry"])]
        result = keyword_recall("上传超时", notes)
        self.assertEqual([note["id"] for note in result["notes"]], ["n1"])
        self.assertIn("timeout", result["expanded_tokens"])

    def test_tag_hit_is_high_band(self):
        notes = [Note(id="n1", text="unrelated body", tags=["upload"])]
        result = keyword_recall("upload failed", notes)
        self.assertEqual(result["notes"][0]["band"], "high")
        self.assertEqual(result["notes"][0]["reason"], "direct_structured_cue")

    def test_body_hit_without_tag_is_medium_band(self):
        notes = [Note(id="n1", text="the retry wrapper reuses a stream", tags=["other"])]
        result = keyword_recall("retry stream", notes)
        self.assertEqual(result["notes"][0]["band"], "medium")

    def test_expand_tokens_is_symmetric(self):
        self.assertIn("timeout", expand_tokens(["超时"]))
        self.assertIn("超时", expand_tokens(["timeout"]))


class EvidenceBindTest(unittest.TestCase):
    def test_missing_evidence_fails_verification(self):
        bound = evidence_bind(
            [{"id": "t1", "title": "Reproduce"}, {"id": "t2", "title": "Fix"}],
            {"t1": "reproduced on fixture"},
        )
        self.assertEqual(bound["skill"], BIND_SKILL_NAME)
        self.assertFalse(bound["verified"])
        self.assertTrue(bound["items"][0]["passed"])
        self.assertFalse(bound["items"][1]["passed"])

    def test_complete_evidence_passes(self):
        bound = evidence_bind(
            [{"id": "t1", "title": "Reproduce"}],
            {"t1": "log attached"},
        )
        self.assertTrue(bound["verified"])


class RollbackTest(unittest.TestCase):
    def test_rolled_back_note_is_not_recalled(self):
        store = NoteStore([
            Note(id="keep", text="retry wrapper reuses a stream", tags=["retry"]),
            Note(id="gone", text="retry wrapper reuses a stream", tags=["retry"]),
        ])
        store.rollback("gone")
        result = keyword_recall("retry stream", notes=store.active())
        ids = [note["id"] for note in result["notes"]]
        self.assertIn("keep", ids)
        self.assertNotIn("gone", ids)

    def test_pipeline_rollback_keeps_the_row(self):
        store = NoteStore([
            Note(id="n1", text="retry wrapper reuses a stream on upload", tags=["upload", "retry"]),
        ])
        issue = "Large uploads crash with a timeout on retry; we need a regression test."
        dry = run_pipeline(issue, store)
        evidence = {task.id: "ok %s" % task.id for task in dry.subtasks}
        result = run_pipeline(issue, store, evidence=evidence, approve=approve_always)
        self.assertIsNotNone(result.captured_note_id)
        before = len(store)
        rollback_capture(store, result.captured_note_id)
        self.assertEqual(len(store), before)
        self.assertEqual(
            [n.status for n in store if n.id == result.captured_note_id],
            ["rolled_back"],
        )

    def test_context_packet_auto_injects_only_high_band(self):
        store = NoteStore([
            Note(id="n1", text="retry wrapper reuses a stream", tags=["retry", "upload"]),
        ])
        result = run_pipeline("upload retry timeout", store)
        self.assertIn("n1", result.context["auto_inject"])
        self.assertEqual(result.context["citations"][0]["id"], "n1")


class ReplayTest(unittest.TestCase):
    def test_trace_round_trips_from_disk(self):
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "run.jsonl")
        original = Trace(path=path)
        original.record("pipeline", "task_input", chars=4)
        loaded = Trace.load(path)
        self.assertEqual(loaded.run_id, original.run_id)
        self.assertEqual(loaded.events[0]["event"], "task_input")


if __name__ == "__main__":
    unittest.main()
