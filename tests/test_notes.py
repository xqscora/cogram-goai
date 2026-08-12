import json
import os
import tempfile
import unittest

from cogram_goai.notes import NoteStore, NoteStoreError


class NoteStoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, "notes.json")

    def test_missing_file_gives_empty_store(self):
        store = NoteStore.load(self.path)
        self.assertEqual(len(store), 0)

    def test_round_trip(self):
        store = NoteStore.load(self.path)
        store.append("retry wrapper reuses the stream", tags=["Upload", "retry"])
        store.save()
        reloaded = NoteStore.load(self.path)
        self.assertEqual(len(reloaded), 1)
        self.assertEqual(reloaded.notes[0].tags, ["upload", "retry"])

    def test_dict_form_with_notes_key(self):
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump({"notes": [{"id": "a", "text": "hello", "tags": []}]}, handle)
        self.assertEqual(len(NoteStore.load(self.path)), 1)

    def test_empty_note_rejected(self):
        store = NoteStore.load(self.path)
        with self.assertRaises(NoteStoreError):
            store.append("   ")

    def test_note_without_text_rejected(self):
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump([{"id": "a", "tags": []}], handle)
        with self.assertRaises(NoteStoreError):
            NoteStore.load(self.path)

    def test_secret_looking_paths_are_refused(self):
        for name in (".env", "my_secret_notes.json", "api_token.json"):
            with self.assertRaises(NoteStoreError):
                NoteStore.load(os.path.join(self.tmp, name))


if __name__ == "__main__":
    unittest.main()
