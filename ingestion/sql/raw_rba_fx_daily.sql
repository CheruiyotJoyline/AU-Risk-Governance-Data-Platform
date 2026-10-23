-- RBA F11.1 as landed: one row per series per business day.
-- rate_value is foreign currency per A$1 (or an index level for FXRTWI).
create table if not exists raw.rba_fx_daily (
    series_id text not null,
    rate_date date not null,
    rate_value numeric(18, 6) not null,
    units text not null,
    title text not null,
    publication_date date,
    _loaded_at timestamptz not null,
    _source_file text not null,
    _row_hash char(32) not null,
    primary key (series_id, rate_date)
);
