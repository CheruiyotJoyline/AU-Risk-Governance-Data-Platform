"""Helpers shared by every ingestion job: download, row hashing, DDL and load logging."""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import requests

SQL_DIR = Path(__file__).parent / "sql"
USER_AGENT = "AU-Risk-Governance-Data-Platform (github.com/CheruiyotJoyline)"


def download(url: str, dest: Path, timeout: int = 60) -> Path:
    """Stream ``url`` to ``dest`` and return the path. Raises on any non-2xx response."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with requests.get(url, headers={"User-Agent": USER_AGENT}, stream=True, timeout=timeout) as r:
        r.raise_for_status()
        with tmp.open("wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 16):
                f.write(chunk)
    # Rename only after a complete download, so a failed run never leaves a half file behind.
    tmp.replace(dest)
    return dest


def row_hash(*values: object) -> str:
    """md5 of the business columns. None and "" hash differently on purpose."""
    joined = "\x1f".join("\x00" if v is None else str(v) for v in values)
    return hashlib.md5(joined.encode("utf-8"), usedforsecurity=False).hexdigest()


def run_sql_file(conn, name: str) -> None:
    """Execute a file from ingestion/sql. Files must be idempotent (IF NOT EXISTS)."""
    with conn.cursor() as cur:
        cur.execute((SQL_DIR / name).read_text())
    conn.commit()


@dataclass
class LoadStats:
    rows_read: int = 0
    rows_inserted: int = 0
    rows_updated: int = 0
    extra: dict = field(default_factory=dict)


@contextmanager
def load_log(
    conn,
    *,
    source: str,
    target_table: str,
    source_file: str,
    run_id: str | None = None,
) -> Iterator[LoadStats]:
    """Record one load in audit.load_log, whether it succeeds or fails.

    The log row is written on a fresh transaction after the load commits or
    rolls back, so a failed load still leaves a trace.
    """
    stats = LoadStats()
    started_at = datetime.now(UTC)
    status, error = "success", None
    try:
        yield stats
    except Exception as exc:
        conn.rollback()
        status, error = "failed", repr(exc)[:2000]
        raise
    finally:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into audit.load_log
                    (source, target_table, source_file, run_id, rows_read,
                     rows_inserted, rows_updated, status, error, started_at, finished_at)
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
                """,
                (
                    source,
                    target_table,
                    source_file,
                    run_id,
                    stats.rows_read,
                    stats.rows_inserted,
                    stats.rows_updated,
                    status,
                    error,
                    started_at,
                ),
            )
        conn.commit()
