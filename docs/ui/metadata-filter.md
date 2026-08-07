
# Metadata Filter

The page contains Exchange, Instrument Type, Country, Currency, and Name filters.
Selecting a project in the persistent project menu loads that project's saved
filter values into all five fields.
After a selection is created, quote-fetch progress is shown first. Beneath the
progress bar, the `Fetch quotes` button is aligned to the right and calls
`POST /api/quote-runs` with the current metadata selection id. Progress is loaded
from `GET /api/quote-runs/{run_id}` and remains server-owned. The determinate
bar and status text show completed provider tasks out of the server-reported
total while the run is active.
