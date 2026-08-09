# Multivariate Input Snapshot

`portfell.multivariate_inputs` owns the immutable hand-off into Multivariate
Statistics. A `MultivariateInputSnapshot` is constructed only from an already
authorised project dependency closure; it never reads a global current
selection, scans the lake, or starts ingestion, Univariate, or Bivariate work.

The initial `MonthlyDistributionEtfPolicy` is explicit and versioned. It
requires typed `instrument_type=ETF`, typed `distribution_frequency=monthly`,
production-eligible quote history, two or more distinct `(isin, exchange,
code)` listing keys, and 504 shared daily return observations. Frequency is an
eligibility criterion, not a claim about income quality or sustainability.

Each snapshot pins the project snapshot, metadata selection, Univariate run and
selection, Bivariate run, sorted full listing keys, quote/dividend artifact
identities, aligned calendar, period, observation count, policy, and a
deterministic dependency hash. Rejections are persisted as stable reason codes;
there is no implicit fallback to a newer selection or a weaker policy.

Both local and hosted callers use `ExplicitMultivariateInputAdapter` after they
have resolved and authorised their inputs. Later Multivariate services must
persist and authorize the resulting snapshot id, not reconstruct authority from
browser values or latest/current pointers.
