from __future__ import annotations

from portfell.multivariate_refits import _ordered_refit_candidate_sets


def test_refit_batches_are_reassembled_in_chronological_start_order() -> None:
    first = ({"candidate_id": "start-2"},)
    second = ({"candidate_id": "start-0"},)
    third = ({"candidate_id": "start-1"},)
    ordered = _ordered_refit_candidate_sets((((2, first), (1, third)), ((0, second),)))
    assert [row[0]["candidate_id"] for row in ordered] == [
        "start-0",
        "start-1",
        "start-2",
    ]
