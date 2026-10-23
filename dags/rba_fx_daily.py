"""Daily RBA exchange rates (table F11.1) into raw.rba_fx_daily.

Each run downloads the whole current file and upserts it. Unchanged rows are
skipped by row hash, so clearing and re-running any run is safe.
"""

from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

import pendulum
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.sdk import dag, task
from airflow.timetables.trigger import CronTriggerTimetable

from ingestion.common import download, load_log, run_sql_file
from ingestion.rba import fx

CONN_ID = "warehouse_loader"
LANDING = Path(os.environ.get("LANDING_DIR", "/opt/airflow/data/landing")) / "rba"


@dag(
    # The RBA publishes F11.1 around 4pm Sydney time on business days.
    schedule=CronTriggerTimetable("0 17 * * 1-5", timezone="Australia/Sydney"),
    start_date=pendulum.datetime(2026, 10, 1, tz="Australia/Sydney"),
    catchup=False,
    max_active_runs=1,
    default_args={
        "retries": 3,
        "retry_delay": timedelta(minutes=5),
        "retry_exponential_backoff": True,
    },
    tags=["ingestion", "rba", "fx"],
)
def rba_fx_daily():
    @task
    def ensure_tables() -> None:
        conn = PostgresHook(postgres_conn_id=CONN_ID).get_conn()
        try:
            run_sql_file(conn, "audit_load_log.sql")
            run_sql_file(conn, "raw_rba_fx_daily.sql")
        finally:
            conn.close()

    @task
    def extract() -> str:
        # Name by download time: manual runs in Airflow 3 have no logical date,
        # and the timestamp records exactly which copy of the file was loaded.
        stamp = pendulum.now("UTC").format("YYYYMMDD[T]HHmmss[Z]")
        return str(download(fx.URL, LANDING / f"f11.1_{stamp}.csv"))

    @task
    def load(path: str, run_id: str | None = None) -> dict:
        rates = fx.parse_f11(Path(path))
        conn = PostgresHook(postgres_conn_id=CONN_ID).get_conn()
        try:
            with load_log(
                conn, source="rba_f11.1", target_table=fx.TABLE, source_file=path, run_id=run_id
            ) as stats:
                stats.rows_read = len(rates)
                stats.rows_inserted, stats.rows_updated = fx.upsert(conn, rates, path)
        finally:
            conn.close()
        return {
            "rows_read": stats.rows_read,
            "rows_inserted": stats.rows_inserted,
            "rows_updated": stats.rows_updated,
        }

    ensure_tables() >> load(extract())


rba_fx_daily()
