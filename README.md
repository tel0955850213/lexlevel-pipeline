# LexLevel Dictionary Pipeline

A small, reproducible version of the data pipeline behind LexLevel, an offline English dictionary. Build a SQLite file from JSON Lines entries and a CSV of level labels. The included definitions, example levels, and translations are hand-authored fixtures.

## Run it

Use Python 3.9 or later. The builder uses only the standard library.

```sh
git clone https://github.com/tel0955850213/lexlevel-pipeline.git
cd lexlevel-pipeline
python3 build_dictionary.py
python3 -m unittest -v
sqlite3 build/demo.sqlite 'SELECT word, pos, level, level_method FROM entries ORDER BY word, pos;'
```

The demo produces four entries. Three have translations. One level is estimated. Use a fresh `--output` path on a second run.

## Decisions in the pipeline

- Merge entries by normalized headword and part of speech. A repeated definition keeps its source tags.
- Prefer a label for that exact word and part of speech, then a headword label. Store frequency-based estimates separately so the app can mark them as estimates.
- Write an indexed SQLite database and report translation coverage. Coverage measures whether a translation exists.

To use your own inputs, start with the schemas in [fixtures](fixtures/) and pass `--entries`, `--levels`, and `--output`. The production corpus, generated production database, and enrichment services are outside this demo. Only use content you have permission to process and redistribute.

The demo code and bundled fixtures are available under the [MIT license](LICENSE).
