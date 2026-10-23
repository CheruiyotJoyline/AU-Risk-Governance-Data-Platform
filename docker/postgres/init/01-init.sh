#!/usr/bin/env bash
# Runs once, the first time the postgres-data volume is created.
# To re-run it: make reset (drops the volume and all data).
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<-SQL
	-- Airflow metadata lives in its own database, away from the warehouse.
	CREATE ROLE airflow LOGIN PASSWORD '${AIRFLOW_DB_PASSWORD}';
	CREATE DATABASE airflow OWNER airflow;

	-- One login role per job. See docs/adr/0001-warehouse-layout-and-roles.md.
	CREATE ROLE loader LOGIN PASSWORD '${LOADER_PASSWORD}';
	CREATE ROLE transformer LOGIN PASSWORD '${TRANSFORMER_PASSWORD}';
	CREATE ROLE reporter LOGIN PASSWORD '${REPORTER_PASSWORD}';

	CREATE DATABASE warehouse;
	REVOKE ALL ON DATABASE warehouse FROM PUBLIC;
	GRANT CONNECT ON DATABASE warehouse TO loader, transformer, reporter;
SQL

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname warehouse <<-SQL
	REVOKE ALL ON SCHEMA public FROM PUBLIC;

	CREATE SCHEMA raw;
	CREATE SCHEMA staging;
	CREATE SCHEMA marts;
	CREATE SCHEMA audit;

	-- loader: lands source data and records each load.
	GRANT USAGE, CREATE ON SCHEMA raw, audit TO loader;

	-- transformer (dbt): reads raw and audit, builds staging and marts.
	GRANT USAGE ON SCHEMA raw, audit TO transformer;
	GRANT USAGE, CREATE ON SCHEMA staging, marts TO transformer;
	ALTER DEFAULT PRIVILEGES FOR ROLE loader IN SCHEMA raw, audit
	    GRANT SELECT ON TABLES TO transformer;

	-- reporter (Superset): reads marts and nothing else.
	GRANT USAGE ON SCHEMA marts TO reporter;
	ALTER DEFAULT PRIVILEGES FOR ROLE transformer IN SCHEMA marts
	    GRANT SELECT ON TABLES TO reporter;
SQL
