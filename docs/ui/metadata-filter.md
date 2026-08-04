
# Metadata Filter

The page contains Exchange, Instrument Type, Country, Currency, and Name filters.
After a selection is created, quote-fetch progress is shown first. Beneath the
progress bar, the `Fetch quotes` button is aligned to the right and calls
`POST /api/data/load-selected-isins`, which invokes `fetch-all-quotes` for the
current metadata selection.
