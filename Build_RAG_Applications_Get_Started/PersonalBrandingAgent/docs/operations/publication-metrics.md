# Publication engagement metrics — safe manual import

The branding agent records what it published. It does **not** read post
performance: there is no metrics API binding, and the application makes no live
external calls. Engagement numbers are therefore imported **by hand**, from an
export you download, and used only to *read* how posts did. Nothing in the
pipeline consumes them; importing a file changes no decision, no backlog row,
and no publication record.

## What an import is

One CSV row is one reading of one post's engagement **at one age**:

| column           | required | meaning                                          |
| ---------------- | -------- | ------------------------------------------------ |
| `publication_id` | yes      | a publication the store already holds            |
| `age_hours`      | yes      | the post's age, in hours, when these were read   |
| `impressions`    | no       | defaults to `0`                                  |
| `reactions`      | no       | defaults to `0`                                  |
| `comments`       | no       | defaults to `0`                                  |
| `reposts`        | no       | defaults to `0`                                  |
| `source`         | no       | defaults to `manual`                             |

Example:

```csv
publication_id,age_hours,impressions,reactions,comments,reposts,source
pub_abc123,6,1840,22,5,2,manual
pub_abc123,168,5210,61,14,7,manual
```

A post appearing at several ages is expected and encouraged — that is what
makes an honest comparison possible (see below). Readings are kept, never
merged.

## Importing

Dry run first (this writes nothing):

```bash
.venv/bin/python -m app.metrics.import_metrics metrics.csv
```

Then, when the dry run lists exactly what you expect:

```bash
.venv/bin/python -m app.metrics.import_metrics metrics.csv --apply
```

Flags: `--database PATH` targets a non-default store; `--source NAME` overrides
the source recorded on every row.

## Why it is safe

- **All-or-nothing parse.** Any bad row (missing value, non-number, negative
  count, unknown column, a row with more fields than the header) fails the
  whole file, so a single typo imports *nothing* rather than importing the rest
  and leaving a half-applied reading.
- **Known publications only.** Every `publication_id` is checked against the
  store *before* the first write; an unknown id makes the import write nothing.
- **Dry run by default.** The store changes only when `--apply` is passed.
- **One table.** The importer writes only `publication_metrics` (migration 12).
  It never touches publications, intents, opportunities, or runs.

Exit codes: `0` success (including a dry run), `2` the file or a referenced
publication is invalid.

## Comparing by age

A 6-hour-old post cannot be judged against a 30-day-old one. The store compares
at a **comparable age**:

```python
store.comparable_age_baseline(6, tolerance_hours=6)      # peaks at ≈6h old
store.compare_publication_to_baseline(publication_id)     # vs its own peers
```

The baseline reports the count of comparable readings and averages across
them; with nothing comparable the averages are `None`, never a misleading
`0.0`. `compare_publication_to_baseline` uses a post's own latest reading age,
so the comparison is always at the age it was last measured, and excludes the
post from its own baseline.

## A note on provenance

Metrics are a report, not evidence. They are never written into a publication's
evidence, and a baseline is never an input to the agent's decision to publish.
Discoverability improvements (Phase 6) are judged by this comparison across
posts of the same age — a human reading, at human pace.
