create table if not exists audit.load_log (
    load_id bigint generated always as identity primary key,
    source_name text not null,
    target_table text not null,
    source_file text,
    run_id text,
    rows_read integer not null default 0,
    rows_inserted integer not null default 0,
    rows_updated integer not null default 0,
    status text not null check (status in ('success', 'failed')),
    error text,
    started_at timestamptz not null,
    finished_at timestamptz not null
);

create index if not exists load_log_target_started_idx
on audit.load_log (target_table, started_at desc);
