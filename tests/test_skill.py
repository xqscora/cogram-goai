import unittest

from cogram_goai.notes import Note
from cogram_goai.skill import SKILL_CONTRACT, SKILL_NAME, keyword_recall

NOTES = [
    Note(id="n1", text="Uploads time out because the retry wrapper reuses a stream", tags=["upload", "retry"]),
    Note(id="n2", text="Login 500s were caused by an expired signing key", tags=["login", "auth"]),
    Note(id="n3", text="Upload regression tests need a large fixture", tags=["upload", "test"]),
]


class KeywordRecallTest(unittest.TestCase):
    def test_returns_matching_notes_sorted_by_score(self):
        result = keyword_recall("upload retry timeout", NOTES)
        ids = [note["id"] for note in result["notes"]]
        self.assertIn("n1", ids)
        self.assertNotIn("n2", ids)
        scores = [note["score"] for note in result["notes"]]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_tag_hits_are_reported(self):
        result = keyword_recall("upload retry", NOTES)
        self.assertIn("upload", result["matched_tags"])
        self.assertIn("retry", result["matched_tags"])

    def test_matched_tags_only_come_from_returned_notes(self):
        result = keyword_recall("upload retry login", NOTES, max_notes=1)
        self.assertNotIn("login", result["matched_tags"])

    def test_max_notes_is_respected(self):
        result = keyword_recall("upload", NOTES, max_notes=1)
        self.assertEqual(len(result["notes"]), 1)

    def test_no_match_falls_back_instead_of_raising(self):
        result = keyword_recall("please repaint the bikeshed", NOTES)
        self.assertEqual(result["notes"], [])
        self.assertEqual(result["fallback"], "manual_search")

    def test_min_score_filters_weak_hits(self):
        loose = keyword_recall("upload", NOTES, min_score=1.0)
        strict = keyword_recall("upload", NOTES, min_score=5.0)
        self.assertTrue(loose["notes"])
        self.assertEqual(strict["notes"], [])

    def test_chinese_issue_text_matches_chinese_note(self):
        notes = [Note(id="z1", text="超时通常来自重试逻辑", tags=["timeout"])]
        result = keyword_recall("上传超时怎么办", notes)
        self.assertEqual([note["id"] for note in result["notes"]], ["z1"])

    def test_invalid_max_notes_rejected(self):
        with self.assertRaises(ValueError):
            keyword_recall("upload", NOTES, max_notes=0)

    def test_contract_declares_the_required_fields(self):
        for key in ("name", "purpose", "input", "output", "invocation", "failure_mode", "security"):
            self.assertIn(key, SKILL_CONTRACT)
        self.assertEqual(SKILL_CONTRACT["name"], SKILL_NAME)


if __name__ == "__main__":
    unittest.main()
