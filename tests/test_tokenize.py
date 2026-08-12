import unittest

from cogram_goai.tokenize import normalize_tags, token_set, tokenize


class TokenizeTest(unittest.TestCase):
    def test_stopwords_and_short_tokens_are_dropped(self):
        self.assertEqual(tokenize("the a of upload"), ["upload"])

    def test_tokens_are_deduplicated_in_order(self):
        self.assertEqual(tokenize("retry upload retry"), ["retry", "upload"])

    def test_chinese_is_split_into_bigrams(self):
        self.assertIn("超时", token_set("上传超时"))

    def test_single_chinese_character_survives(self):
        self.assertIn("慢", token_set("慢"))

    def test_empty_text(self):
        self.assertEqual(tokenize(""), [])

    def test_tags_are_lowercased_and_deduplicated(self):
        self.assertEqual(normalize_tags([" Upload ", "upload", "RETRY"]), ["upload", "retry"])


if __name__ == "__main__":
    unittest.main()
