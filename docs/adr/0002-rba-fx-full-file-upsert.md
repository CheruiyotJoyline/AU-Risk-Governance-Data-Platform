# 0002. Load RBA FX rates as a full-file upsert

- Status: accepted
- Date: 2026-10-23

## Context

The RBA publishes daily exchange rates as one CSV (table F11.1) covering 2023 to today. There's no API for a single day, and the file is small: about 19,000 rows once unpivoted. Older years are in separate history files.

## Decision

Each run downloads the whole file and upserts every row into `raw.rba_fx_daily` on `(series_id, rate_date)`.

- `_row_hash` is the md5 of `series_id`, `rate_date`, `rate_value` and `units`. An existing row is only updated when its hash changes.
- `publication_date` is stored but left out of the hash. It changes every day on every row, so including it would rewrite the whole table on each run.
- Each downloaded file is kept in `data/landing/rba/` with the run date in its name, and `_source_file` points at it.
- Blank cells (no rate that day) are skipped rather than stored as nulls.
- `catchup` is off. Re-running a past date gives the same result as running today, because the file always holds the full history.

## Consequences

- Re-running any DAG run is a no-op when nothing has changed: 0 rows inserted, 0 updated in `audit.load_log`.
- RBA revisions to past rates are picked up automatically and show up as updates.
- `_loaded_at` records when a value last changed, not when it was last seen.
- Loading pre-2023 history needs a one-off DAG for the history files. It can reuse `parse_f11` if their layout matches.
