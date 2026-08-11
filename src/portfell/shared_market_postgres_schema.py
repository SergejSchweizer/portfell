"""D021 shared, tenant-neutral market-data tables."""

SHARED_MARKET_POSTGRES_SCHEMA_SQL = """
create table if not exists portfell_app.shared_market_metadata (
    provider text not null,
    exchange text not null,
    code text not null,
    isin text not null,
    document jsonb not null,
    updated_at timestamptz not null default now(),
    primary key (provider, exchange, code, isin)
);

create table if not exists portfell_app.shared_market_rows (
    dataset_type text not null check (dataset_type in ('quotes', 'dividends', 'splits')),
    provider text not null,
    exchange text not null,
    code text not null,
    isin text not null,
    business_key text not null,
    document jsonb not null,
    updated_at timestamptz not null default now(),
    primary key (dataset_type, provider, exchange, code, isin, business_key)
);

create table if not exists portfell_app.shared_market_coverage (
    dataset_type text not null check (dataset_type in ('quotes', 'dividends', 'splits')),
    provider text not null,
    exchange text not null,
    code text not null,
    isin text not null,
    first_business_date date,
    last_business_date date,
    row_count integer not null check (row_count >= 0),
    content_hash text not null,
    updated_at timestamptz not null default now(),
    primary key (dataset_type, provider, exchange, code, isin)
);

create index if not exists shared_market_metadata_filter_index
on portfell_app.shared_market_metadata (exchange, isin, code);

create index if not exists shared_market_rows_listing_index
on portfell_app.shared_market_rows (dataset_type, provider, exchange, isin, code, business_key);
"""
