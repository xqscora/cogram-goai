import json
import os
import tempfile
import unittest

from cogram_goai.notes import Note, NoteStore
from cogram_goai.pipeline import approve_always, approve_never, run_pipeline
from cogram_goai.trace import Trace

ISSUE = "Large uploads crash with a timeout on retry; we need a regression test."


def _store():
    return NoteStore(
        [
            Note(id="n1", text="retry wrapper reuses a consumed stream on upload", tags=["upload", "retry"]),
            Note(id="n2", text="login 500s came from an expired key", tags=["login"]),
        ]
    )


def _evidence(result):
    return {task.id: "evidence for %s" % task.id for task in result.subtasks}


class PipelineTest(unittest.TestCase):
    def test_without_evidence_the_gate_is_never_reached(self):
        result = run_pipeline(ISSUE, _store(), approve=approve_always)
        self.assertFalse(result.verified)
        self.assertIsNone(result.approved)
        self.assertEqual(len(result.trace.by_event("gate_skipped")), 1)

    def test_verified_run_without_approver_stays_pending(self):
        store = _store()
        dry = run_pipeline(ISSUE, store)
        result = run_pipeline(ISSUE, store, evidence=_evidence(dry))
        self.assertTrue(result.verified)
        self.assertIsNone(result.approved)
        self.assertEqual(len(result.trace.by_event("gate_pending")), 1)

    def test_approved_run_captures_a_note(self):
        store = _store()
        dry = run_pipeline(ISSUE, store)
        before = len(store)
        result = run_pipeline(ISSUE, store, evidence=_evidence(dry), approve=approve_always)
        self.assertTrue(result.approved)
        self.assertEqual(len(store), before + 1)
        self.assertIsNotNone(result.captured_note_id)

    def test_rejected_run_captures_nothing(self):
        store = _store()
        dry = run_pipeline(ISSUE, store)
        before = len(store)
        result = run_pipeline(ISSUE, store, evidence=_evidence(dry), approve=approve_never)
        self.assertFalse(result.approved)
        self.assertEqual(len(store), before)
        self.assertIsNone(result.captured_note_id)

    def test_recall_is_passed_between_agents(self):
        result = run_pipeline(ISSUE, _store())
        self.assertTrue(result.recall["notes"])
        self.assertEqual(result.recall["notes"][0]["id"], "n1")

    def test_trace_covers_the_whole_loop(self):
        store = _store()
        dry = run_pipeline(ISSUE, store)
        result = run_pipeline(ISSUE, store, evidence=_evidence(dry), approve=approve_always)
        events = [entry["event"] for entry in result.trace.events]
        for expected in (
            "task_input",
            "decomposition",
            "skill_call",
            "verification",
            "human_approval",
            "experience_capture",
        ):
            self.assertIn(expected, events)

    def test_trace_file_is_valid_jsonl(self):
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "run.jsonl")
        trace = Trace(path=path)
        run_pipeline(ISSUE, _store(), trace=trace)
        with open(path, "r", encoding="utf-8") as handle:
            lines = [line for line in handle.read().splitlines() if line.strip()]
        self.assertTrue(lines)
        for line in lines:
            self.assertIn("run_id", json.loads(line))

    def test_captured_note_is_recalled_next_time(self):
        store = _store()
        dry = run_pipeline(ISSUE, store)
        run_pipeline(ISSUE, store, evidence=_evidence(dry), approve=approve_always)
        again = run_pipeline(ISSUE, store)
        self.assertIn(
            "Resolved",
            " ".join(note["text"] for note in again.recall["notes"]),
        )


if __name__ == "__main__":
    unittest.main()
