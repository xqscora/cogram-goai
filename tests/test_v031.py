import os
import tempfile
import unittest

from cogram_goai.agents.triage import TriageClerk
from cogram_goai.notes import Note, NoteStore
from cogram_goai.pipeline import approve_always, issue_hash, run_pipeline
from cogram_goai.trace import Trace


ISSUE = "Large uploads crash with a timeout on retry; we need a regression test."


def _store():
    return NoteStore(
        [
            Note(
                id="n1",
                text="retry wrapper reuses a consumed stream on upload",
                tags=["upload", "retry"],
            ),
        ]
    )


class ProvenanceTest(unittest.TestCase):
    def test_issue_hash_is_stable_under_whitespace(self):
        self.assertEqual(issue_hash("a  b\n c"), issue_hash("a b c"))
        self.assertEqual(len(issue_hash("x")), 16)

    def test_capture_records_run_id_and_issue_hash(self):
        store = _store()
        dry = run_pipeline(ISSUE, store)
        evidence = {task.id: "ok %s" % task.id for task in dry.subtasks}
        result = run_pipeline(ISSUE, store, evidence=evidence, approve=approve_always)
        captured = next(note for note in store if note.id == result.captured_note_id)
        self.assertEqual(captured.issue_hash, result.issue_hash)
        self.assertEqual(captured.run_id, result.run_id)
        self.assertTrue(captured.issue_hash)

    def test_second_approved_run_does_not_duplicate(self):
        store = _store()
        dry = run_pipeline(ISSUE, store)
        evidence = {task.id: "ok %s" % task.id for task in dry.subtasks}
        first = run_pipeline(ISSUE, store, evidence=evidence, approve=approve_always)
        before = len(store)
        second = run_pipeline(ISSUE, store, evidence=evidence, approve=approve_always)
        self.assertEqual(len(store), before)
        self.assertEqual(first.captured_note_id, second.captured_note_id)
        capture = second.trace.by_event("experience_capture")[0]
        self.assertTrue(capture["payload"]["deduped"])


class CitedCaptureTest(unittest.TestCase):
    def test_capture_lists_the_notes_that_were_in_context(self):
        store = _store()
        dry = run_pipeline(ISSUE, store)
        evidence = {task.id: "ok %s" % task.id for task in dry.subtasks}
        result = run_pipeline(ISSUE, store, evidence=evidence, approve=approve_always)
        captured = next(note for note in store if note.id == result.captured_note_id)
        self.assertIn("n1", captured.cited)
        self.assertEqual(captured.cited, [item["id"] for item in result.context["citations"]])


class UniqueEvidenceTest(unittest.TestCase):
    def test_copy_pasted_ok_fails_the_checklist(self):
        from cogram_goai.skill import evidence_bind

        bound = evidence_bind(
            [{"id": "t1", "title": "repro"}, {"id": "t2", "title": "fix"}],
            {"t1": "ok", "t2": "ok"},
        )
        self.assertFalse(bound["verified"])
        self.assertTrue(bound["items"][0]["passed"])
        self.assertFalse(bound["items"][1]["passed"])
        self.assertTrue(bound["items"][1]["evidence"].startswith("(reused)"))


class SecurityTriageTest(unittest.TestCase):
    def test_oauth_issue_gets_a_secure_subtask(self):
        kinds = [task.kind for task in TriageClerk().run("oauth cors leak on the login page")]
        self.assertIn("secure", kinds)
        self.assertIn("locate", kinds)
        self.assertLessEqual(len(kinds), 3)

    def test_plain_crash_does_not_invent_a_secure_subtask(self):
        kinds = [task.kind for task in TriageClerk().run("The upload crashes with a traceback on retry")]
        self.assertNotIn("secure", kinds)


class CompleteTraceTest(unittest.TestCase):
    def test_finished_run_is_complete(self):
        store = _store()
        dry = run_pipeline(ISSUE, store)
        evidence = {task.id: "ok %s" % task.id for task in dry.subtasks}
        result = run_pipeline(ISSUE, store, evidence=evidence, approve=approve_always)
        self.assertEqual(result.trace.verify_complete(), [])

    def test_partial_trace_is_incomplete(self):
        trace = Trace()
        trace.record("pipeline", "task_input", chars=1)
        errors = trace.verify_complete()
        self.assertTrue(any("missing event" in item for item in errors))

    def test_verify_complete_cli_flag(self):
        from cogram_goai.cli import main
        import io
        from contextlib import redirect_stdout

        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "run.jsonl")
        store = _store()
        dry = run_pipeline(ISSUE, store)
        evidence = {task.id: "ok %s" % task.id for task in dry.subtasks}
        run_pipeline(ISSUE, store, evidence=evidence, approve=approve_always, trace=Trace(path=path))
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["verify-trace", "--trace", path, "--complete"])
        self.assertEqual(code, 0)
        self.assertIn("complete run", buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
