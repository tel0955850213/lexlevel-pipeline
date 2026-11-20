"""Build a small, offline SQLite dictionary from source-tagged JSONL and CSV."""

import argparse
from collections import Counter
import csv
import json
import os
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory


FIXTURES = Path(__file__).resolve().parent / "fixtures"
LEVELS = {"A1", "A2", "B1", "B2", "C1", "C2"}
SCHEMA = """
CREATE TABLE entries (
    word TEXT COLLATE NOCASE NOT NULL,
    pos TEXT NOT NULL,
    level TEXT NOT NULL,
    level_source TEXT NOT NULL,
    level_method TEXT NOT NULL CHECK (level_method IN ('exact', 'headword', 'estimated')),
    frequency REAL NOT NULL,
    senses TEXT NOT NULL,
    translations TEXT NOT NULL,
    PRIMARY KEY (word, pos)
);
CREATE INDEX by_level ON entries(level, frequency DESC);
"""


def key(word):
    return word.strip().casefold()


def read_levels(path):
    levels = {}
    with path.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            word, pos = key(row["word"]), key(row["pos"])
            level, provenance = row["level"].strip().upper(), row["source"].strip()
            if not word or level not in LEVELS or not provenance:
                raise ValueError("A level row must have a word, A1–C2 label, and source.")
            entry = (level, provenance)
            if levels.setdefault((word, pos), entry) != entry:
                raise ValueError(f"Conflicting labels for {word} ({pos or 'headword'}).")
    return levels


def merge_entries(path):
    entries = {}
    with path.open(encoding="utf-8-sig") as source:
        for line in source:
            if not line.strip():
                continue
            row = json.loads(line)
            word, pos = key(row["word"]), key(row["pos"])
            if not word or not pos:
                raise ValueError("Each entry needs a word and a part of speech.")
            frequency = float(row["frequency"])
            item = entries.setdefault((word, pos), dict(frequency=frequency, senses={}, translations=set()))
            item["frequency"] = max(item["frequency"], frequency)
            for sense in row["senses"]:
                definition, provenance = sense["definition"].strip(), sense["source"].strip()
                if not definition or not provenance:
                    raise ValueError("Each sense needs a definition and a source.")
                item["senses"].setdefault(definition, set()).add(provenance)
            item["translations"].update(value.strip() for value in row["translations"] if value.strip())
    return entries


def assign_level(levels, word, pos, frequency):
    if (word, pos) in levels:
        return (*levels[(word, pos)], "exact")
    if (word, "") in levels:
        return (*levels[(word, "")], "headword")
    level = "B2" if frequency >= 4.5 else "C1" if frequency >= 3.8 else "C2"
    return level, "frequency-heuristic", "estimated"


def build(entries_path, levels_path, output):
    if output.exists():
        raise FileExistsError(f"Output already exists: {output}")
    levels, entries = read_levels(levels_path), merge_entries(entries_path)
    coverage = Counter({"entries": 0, "translated": 0, "estimated": 0})
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output.parent) as scratch:
        staging = Path(scratch) / "dictionary.sqlite"
        database = sqlite3.connect(staging)
        try:
            with database:
                database.executescript(SCHEMA)
                for (word, pos), item in sorted(entries.items()):
                    senses = [
                        {"definition": definition, "sources": sorted(sources)}
                        for definition, sources in sorted(item["senses"].items())
                    ]
                    if not senses:
                        continue
                    level, source, method = assign_level(levels, word, pos, item["frequency"])
                    translations = sorted(item["translations"])
                    database.execute("INSERT INTO entries VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (
                        word, pos, level, source, method, item["frequency"],
                        json.dumps(senses, ensure_ascii=False), json.dumps(translations, ensure_ascii=False),
                    ))
                    coverage["entries"] += 1
                    coverage["translated"] += bool(translations)
                    coverage["estimated"] += method == "estimated"
        finally:
            database.close()
        # Publish a complete file and fail if the destination appeared during the build.
        os.link(staging, output)
    return dict(coverage)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entries", type=Path, default=FIXTURES / "entries.jsonl")
    parser.add_argument("--levels", type=Path, default=FIXTURES / "levels.csv")
    parser.add_argument("--output", type=Path, default=Path("build/demo.sqlite"))
    args = parser.parse_args()
    try:
        result = build(args.entries, args.levels, args.output)
    except (KeyError, ValueError, OSError) as error:
        parser.exit(1, f"{error}\n")
    print(json.dumps({"database": str(args.output), **result}))


if __name__ == "__main__":
    main()
