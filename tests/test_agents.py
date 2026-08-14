import unittest

from cogram_goai.agents import ChecklistVerifier, KeywordMemoryAgent, TriageClerk
from cogram_goai.notes import Note, NoteStore
from cogram_goai.trace import Trace


class TriageClerkTest(unittest.TestCase):
    def test_error_issue_starts_with_reproduce(self):
        tasks = TriageClerk().run("The upload crashes with a traceback on retry")
        self.assertEqual(tasks[0].kind, "reproduce")
        self.assertLessEqual(len(tasks), 3)

    def test_performance_issue_starts_with_measure(self):
        tasks = TriageClerk().run("The dashboard is slow and hits a timeout")
        self.assertEqual(tasks[0].kind, "measure")

    def test_test_cue_upgrades_the_fix_subtask(self):
        tasks = TriageClerk().run("Upload breaks; we need a regression test")
        self.assertEqual(tasks[-1].kind, "fix_with_test")

    def test_plain_issue_still_gets_locate_and_fix(self):
        kinds = [task.kind for task in TriageClerk().run("Rename the landing page headline")]
        self.assertEqual(kinds[:2], ["locate", "fix"])

    def test_trace_records_decomposition(self):
        trace = Trace()
        TriageClerk().run("upload crashes", trace=trace)
        self.assertEqual(len(trace.by_event("decomposition")), 1)


class KeywordMemoryAgentTest(unittest.TestCase):
    def setUp(self):
        self.store = NoteStore([Note(id="n1", text="retry wrapper reuses the stream", tags=["retry"])])
        self.agent = KeywordMemoryAgent(self.store)

    def test_recall_traces_the_skill_call(self):
        trace = Trace()
        result = self.agent.recall("retry wrapper", trace=trace)
        self.assertEqual(len(result["notes"]), 1)
        call = trace.by_event("skill_call")[0]
        self.assertEqual(call["payload"]["skill"], "cogram.keyword_recall")

    def test_capture_appends_without_a_path(self):
        note = self.agent.capture("new lesson", tags=["retry"])
        self.assertEqual(len(self.store), 2)
        self.assertEqual(note.tags, ["retry"])

    def test_context_lines_explain_a_miss(self):
        lines = self.agent.context_lines(self.agent.recall("unrelated bikeshed"))
        self.assertIn("manual_search", lines[0])


class ChecklistVerifierTest(unittest.TestCase):
    def setUp(self):
        self.tasks = TriageClerk().run("Upload crashes with a traceback")

    def test_missing_evidence_fails_the_item(self):
        items = ChecklistVerifier().run(self.tasks, evidence={})
        self.assertFalse(ChecklistVerifier.all_passed(items))
        self.assertTrue(all(item.evidence == "(missing)" for item in items))

    def test_full_evidence_passes(self):
        evidence = {task.id: "log line for %s" % task.id for task in self.tasks}
        items = ChecklistVerifier().run(self.tasks, evidence=evidence)
        self.assertTrue(ChecklistVerifier.all_passed(items))

    def test_empty_checklist_is_not_a_pass(self):
        self.assertFalse(ChecklistVerifier.all_passed([]))


if __name__ == "__main__":
    unittest.main()
