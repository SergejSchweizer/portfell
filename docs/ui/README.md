
# Portfell UI

Portfell has exactly four sequential production pages:

1. `metadata_filter`
2. `univariate_statistics`
3. `univariate_filter`
4. `bivariate_statistics`

The persistent header accepts an EODHD key and invokes `fetch_all_metadata`. The
Metadata Filter page applies the metadata choices, shows quote-fetch progress,
and places the `Fetch quotes` action beneath the progress bar at the lower-right
edge of the panel. No legacy renderer, compatibility route, component catalogue,
or fixture-selection route is part of the production application.
