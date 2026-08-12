import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout

from cogram_goai.cli import DEFAULT_NOTES, main


def _run(argv):
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = main(argv)
    return code, buffer.getvalue()


class CliTest(unittest.TestCase):
    def test_contract_is_json(self):
        code, out = _run(["contract"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["name"], "cogram.keyword_recall")

    def test_skill_on_bundled_notes(self):
        code, out = _run(["skill", "--issue", "upload timeout retry"])
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertTrue(payload["notes"])

    def test_notes_listing(self):
        code, out = _run(["notes"])
        self.assertEqual(code, 0)
        self.assertIn("note(s) in", out)

    def test_run_json_output_with_evidence(self):
        evidence = json.dumps({"t1": "repro", "t2": "located", "t3": "patched"})
        code, out = _run(
            [
                "run",
                "--issue-file",
                os.path.join(os.path.dirname(DEFAULT_NOTES), "issues", "flaky_upload_timeout.txt"),
                "--evidence",
                evidence,
                "--reject",
                "--json",
            ]
        )
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertTrue(payload["verified"])
        self.assertFalse(payload["approved"])

    def test_run_without_evidence_exits_nonzero(self):
        code, _ = _run(["run", "--issue", "something broke", "--json"])
        self.assertEqual(code, 1)

    def test_demo_does_not_touch_the_example_store(self):
        with open(DEFAULT_NOTES, "r", encoding="utf-8") as handle:
            before = handle.read()
        cwd = os.getcwd()
        tmp = tempfile.mkdtemp()
        os.chdir(tmp)
        try:
            code, out = _run(["demo", "--auto-approve", "--trace", os.path.join(tmp, "run.jsonl")])
        finally:
            os.chdir(cwd)
        self.assertEqual(code, 0)
        self.assertIn("[A1 triage]", out)
        with open(DEFAULT_NOTES, "r", encoding="utf-8") as handle:
            self.assertEqual(before, handle.read())
        self.assertTrue(os.path.exists(os.path.join(tmp, "cogram_demo_notes.json")))


if __name__ == "__main__":
    unittest.main()
