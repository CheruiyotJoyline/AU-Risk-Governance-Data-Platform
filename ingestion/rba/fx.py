"""RBA statistical table F11.1: daily exchange rates, quoted as foreign currency per A$1.

File layout (checked 2026-10-23): a title line, then labelled metadata rows
(Title, Description, Frequency, Type, Units, Source, Publication date,
Series ID), then one row per business day with dates like ``23-Oct-2026``.
Blank cells mean no rate that day. The file ends with empty lines.
The current file starts at 2023; earlier years are in separate history files.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from ingestion.common import row_hash

URL = "https://www.rba.gov.au/statistics/tables/csv/f11.1-data.csv"
TABLE = "raw.rba_fx_daily"


@dataclass(frozen=True)
class FxRate:
    series_id: str
    rate_date: date
    value: Decimal
    units: str
    title: str
    publication_date: date | None

    @property
    def hash(self) -> str:
        # publication_date is left out: it changes every day for every row,
        # and including it would rewrite the whole table on each load.
        return row_hash(self.series_id, self.rate_date, self.value, self.units)


def _parse_date(s: str) -> date:
    return datetime.strptime(s.strip(), "%d-%b-%Y").date()


def parse_f11(path: Path) -> list[FxRate]:
    """Turn the wide CSV into one row per series per date, skipping blank cells."""
    meta: dict[str, list[str]] = {}
    rates: list[FxRate] = []

    with path.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.reader(f):
            if not row or not row[0].strip():
                continue
            label = row[0].strip()
            try:
                rate_date = _parse_date(label)
            except ValueError:
                meta[label] = [c.strip() for c in row[1:]]
                continue

            series_ids = meta.get("Series ID")
            if not series_ids:
                raise ValueError(
                    f"{path}: data row before 'Series ID' row; layout may have changed"
                )
            units = meta.get("Units", [])
            titles = meta.get("Title", [])
            published = meta.get("Publication date", [])
            for i, cell in enumerate(row[1 : len(series_ids) + 1]):
                if not cell.strip():
                    continue
                rates.append(
                    FxRate(
                        series_id=series_ids[i],
                        rate_date=rate_date,
                        value=Decimal(cell.strip()),
                        units=units[i] if i < len(units) else "",
                        title=titles[i] if i < len(titles) else "",
                        publication_date=_parse_date(published[i])
                        if i < len(published) and published[i]
                        else None,
                    )
                )
    if "Series ID" not in meta:
        raise ValueError(f"{path} has no 'Series ID' row; the RBA file layout may have changed")
    return rates


def upsert(conn, rates: list[FxRate], source_file: str) -> tuple[int, int]:
    """Insert new rows and update changed ones. Returns (inserted, updated).

    ``conn`` is a psycopg 3 connection, which is what PostgresHook returns
    when psycopg 3 is installed. Rows are COPYed into a temp table, then
    merged with one statement. Rows whose hash is unchanged are skipped, so
    re-running a load is a no-op and _loaded_at keeps the time the value
    last changed.
    """
    cols = (
        "series_id, rate_date, rate_value, units, title, publication_date, "
        "_loaded_at, _source_file, _row_hash"
    )
    loaded_at = datetime.now(UTC)
    with conn.cursor() as cur:
        cur.execute(f"create temp table _stage (like {TABLE}) on commit drop")
        with cur.copy(f"copy _stage ({cols}) from stdin") as copy:
            for r in rates:
                copy.write_row(
                    (
                        r.series_id,
                        r.rate_date,
                        r.value,
                        r.units,
                        r.title,
                        r.publication_date,
                        loaded_at,
                        source_file,
                        r.hash,
                    )
                )
        cur.execute(
            f"""
            insert into {TABLE} ({cols})
            select {cols} from _stage
            on conflict (series_id, rate_date) do update set
                rate_value = excluded.rate_value,
                units = excluded.units,
                title = excluded.title,
                publication_date = excluded.publication_date,
                _loaded_at = excluded._loaded_at,
                _source_file = excluded._source_file,
                _row_hash = excluded._row_hash
            where {TABLE}._row_hash is distinct from excluded._row_hash
            returning (xmax = 0) as inserted
            """
        )
        results = cur.fetchall()
    conn.commit()
    inserted = sum(1 for (is_insert,) in results if is_insert)
    return inserted, len(results) - inserted
