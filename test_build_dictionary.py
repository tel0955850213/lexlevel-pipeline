import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from build_dictionary import FIXTURES, build


class DictionaryTests(unittest.TestCase):
    def test_demo_merges_and_keeps_provenance(self):
        with TemporaryDirectory() as scratch:
            output = Path(scratch) / "fixture.sqlite"
            report = build(FIXTURES / "entries.jsonl", FIXTURES / "levels.csv", output)
            self.assertEqual(report, {"entries": 4, "translated": 3, "estimated": 1})
            database = sqlite3.connect(output)
            try:
                rows = database.execute(
                    "SELECT word, pos, level, level_method FROM entries ORDER BY word, pos"
                ).fetchall()
                self.assertEqual(rows, [
                    ("calibrate", "verb", "C1", "headword"),
                    ("jitter", "noun", "C2", "estimated"),
                    ("relay", "noun", "B1", "exact"),
                    ("relay", "verb", "C1", "exact"),
                ])
                senses = json.loads(database.execute(
                    "SELECT senses FROM entries WHERE word = 'relay' AND pos = 'noun'"
                ).fetchone()[0])
                self.assertEqual(len(senses), 2)
                self.assertIn({
                    "definition": "An electrical switch operated by a separate signal.",
                    "sources": ["fixture-basic", "fixture-extended"],
                }, senses)
            finally:
                database.close()

    def test_existing_database_is_preserved(self):
        with TemporaryDirectory() as scratch:
            output = Path(scratch) / "existing.sqlite"
            output.write_bytes(b"keep me")
            with self.assertRaises(FileExistsError):
                build(FIXTURES / "entries.jsonl", FIXTURES / "levels.csv", output)
            self.assertEqual(output.read_bytes(), b"keep me")
