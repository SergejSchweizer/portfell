CREATE ROLE portfell_app NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
CREATE ROLE portfell LOGIN PASSWORD 'market_reader' NOSUPERUSER NOCREATEDB NOCREATEROLE;
GRANT portfell_app TO portfell;

CREATE SCHEMA xetra_loader AUTHORIZATION market_admin;

CREATE TABLE xetra_loader.listings (
    isin text NOT NULL,
    exchange text NOT NULL,
    code text NOT NULL,
    name text NOT NULL,
    instrument_type text NOT NULL,
    country text,
    currency text,
    is_active boolean NOT NULL,
    PRIMARY KEY (isin, exchange, code)
);
CREATE TABLE xetra_loader.eod_quotes (
    isin text NOT NULL,
    exchange text NOT NULL,
    code text NOT NULL,
    trade_date date NOT NULL,
    adjusted_close numeric,
    close numeric,
    volume numeric,
    PRIMARY KEY (isin, exchange, code, trade_date)
);
CREATE TABLE xetra_loader.dividends (
    isin text NOT NULL,
    exchange text NOT NULL,
    code text NOT NULL,
    event_date date NOT NULL,
    event_key text NOT NULL,
    amount numeric,
    currency text,
    PRIMARY KEY (isin, exchange, code, event_date, event_key)
);
CREATE TABLE xetra_loader.splits (
    isin text NOT NULL,
    exchange text NOT NULL,
    code text NOT NULL,
    event_date date NOT NULL,
    split_ratio text NOT NULL,
    split_factor numeric,
    PRIMARY KEY (isin, exchange, code, event_date, split_ratio)
);

GRANT USAGE ON SCHEMA xetra_loader TO portfell_app;
GRANT SELECT ON ALL TABLES IN SCHEMA xetra_loader TO portfell_app;