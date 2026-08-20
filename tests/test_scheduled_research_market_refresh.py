from portfell.multivariate.contracts.common import ListingIdentity
from portfell.scheduled_research.market_refresh import (
    ActiveProjectUniverse,
    active_union,
    market_cycle_key,
    refresh_active_union_once,
)


def _listing(isin: str, code: str) -> ListingIdentity:
    return ListingIdentity(isin=isin, exchange="XETRA", code=code)


def test_active_union_deduplicates_full_listing_identity_deterministically() -> None:
    a = _listing("DE000A", "AAA")
    b = _listing("DE000B", "BBB")
    projects = (
        ActiveProjectUniverse("beta", (b, a)),
        ActiveProjectUniverse("alpha", (a,)),
    )

    assert active_union(projects) == (a, b)
    assert market_cycle_key(projects=projects, cycle_date="2026-08-23") == market_cycle_key(
        projects=tuple(reversed(projects)), cycle_date="2026-08-23"
    )


def test_refresh_invokes_market_authority_once_for_union() -> None:
    a = _listing("DE000A", "AAA")
    b = _listing("DE000B", "BBB")
    calls: list[tuple[ListingIdentity, ...]] = []

    def refresh(listings: tuple[ListingIdentity, ...]) -> tuple[str, int]:
        calls.append(listings)
        return "market-r1", len(listings) * 3

    result = refresh_active_union_once(
        projects=(ActiveProjectUniverse("a", (a, b)), ActiveProjectUniverse("b", (a,))),
        cycle_date="2026-08-23",
        refresh=refresh,
    )

    assert calls == [(a, b)]
    assert result.listing_count == 2
    assert result.refreshed_business_keys == 6
    assert result.revision == "market-r1"


def test_refresh_rejects_negative_business_key_count() -> None:
    listing = _listing("DE000A", "AAA")

    def refresh(_: tuple[ListingIdentity, ...]) -> tuple[str, int]:
        return "market-r1", -1

    try:
        refresh_active_union_once(
            projects=(ActiveProjectUniverse("a", (listing,)),),
            cycle_date="2026-08-23",
            refresh=refresh,
        )
    except ValueError as exc:
        assert "cannot be negative" in str(exc)
    else:
        raise AssertionError("negative refreshed business-key count must fail closed")
