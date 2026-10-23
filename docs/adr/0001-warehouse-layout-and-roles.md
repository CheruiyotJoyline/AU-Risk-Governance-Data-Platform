# 0001. Warehouse layout and roles

- Status: accepted
- Date: 2026-10-23

## Context

One Postgres instance holds data from several public sources and will later hold fraud, audit and insurance data. Dashboards must never read half-processed data. Each process should get only the access it needs, so a bug in one component cannot damage another layer.

## Decision

Postgres runs two databases: `airflow` (Airflow metadata only) and `warehouse` (all project data).

`warehouse` has four schemas, each with one job:

| Schema    | Holds                                                                                     | Written by                 |
|-----------|-------------------------------------------------------------------------------------------|----------------------------|
| `raw`     | Source data exactly as landed, plus `_loaded_at`, `_source_file` and `_row_hash`          | `loader` (Airflow DAGs)    |
| `staging` | One dbt model per source table: typed, renamed, deduplicated                              | `transformer` (dbt)        |
| `marts`   | Kimball star schemas for reporting                                                        | `transformer` (dbt)        |
| `audit`   | Operational records: `load_log` now, dbt run results later                                | `loader`, later `transformer` |

Each job gets its own login role:

- `loader` can create and write tables in `raw` and `audit`, and has no access to `staging` or `marts`.
- `transformer` reads `raw` and `audit`, and creates tables in `staging` and `marts`.
- `reporter` reads `marts` only. Superset connects with this role.

New tables get these grants automatically through `ALTER DEFAULT PRIVILEGES`, so no one has to remember a `GRANT` after each new model. `PUBLIC` loses all access to the `warehouse` database and its `public` schema.

## Consequences

- The BI layer cannot read `raw` or `staging`, even by mistake. Everything a dashboard shows has passed dbt tests.
- `raw` is never edited by hand, so `staging` and `marts` can always be rebuilt from it.
- Default privileges only apply to tables created by `loader` (in `raw`, `audit`) and `transformer` (in `marts`). Tables created as `postgres` need explicit grants. In practice, only these two roles create tables.
- The init script runs only when the Postgres volume is first created. Changing roles or schemas later needs a migration script, or `make reset` on a dev machine.
- Month 2 adds PII masking views and a governance role on top of this layout.
