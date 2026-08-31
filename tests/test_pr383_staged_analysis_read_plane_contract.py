from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs/contracts/staged-analysis-read-plane-v1.md"


def _contract() -> str:
    return CONTRACT.read_text(encoding="utf-8")


def test_contract_freezes_exact_user_commit_actions_and_no_third_trigger() -> None:
    text = _contract()
    assert "`Create universe & compute Univariate`" in text
    assert "`Apply selection & compute downstream`" in text
    assert "No third normal-flow computation trigger" in text
    assert "Filter preview is read-only" in text
    assert "Selection S" in text
    assert "Multivariate job M(S, B, return_risk)" in text


def test_contract_freezes_job_status_payload_and_transitions() -> None:
    text = _contract()
    for status in ("queued", "running", "succeeded", "failed", "cancelled"):
        assert f"`{status}`" in text
    for transition in (
        "queued -> running",
        "queued -> cancelled",
        "running -> succeeded",
        "running -> failed",
        "running -> cancelled",
    ):
        assert transition in text
    for field in (
        "job_id",
        "stage",
        "status",
        "input_ref",
        "run_id",
        "progress_current",
        "progress_total",
        "progress_phase",
        "attempt",
        "failure_code",
    ):
        assert f"`{field}`" in text
    assert "0 <= progress_current <= progress_total" in text
    assert "monotone non-decreasing" in text


def test_contract_freezes_progress_units_and_multivariate_phases() -> None:
    text = _contract()
    assert "processed members of the persisted Metadata universe" in text
    assert "planned candidate pairs for the persisted Selection" in text
    phases = (
        "inputs",
        "risk_model_and_candidates",
        "walk_forward_validation",
        "scorecards",
        "structural_diagnostics",
        "decision",
        "artifact_persistence",
        "complete",
    )
    positions = [text.index(f"`{phase}`") for phase in phases]
    assert positions == sorted(positions)
    assert "No synthetic Bivariate+Multivariate percentage" in text


def test_contract_freezes_paging_chart_and_payload_caps() -> None:
    text = _contract()
    assert "default page size: `100`" in text
    assert "maximum page size: `500`" in text
    assert "Univariate chart-point cap: `500`" in text
    assert "Bivariate chart-point cap: `1000`" in text
    assert "`<= 512 KiB`" in text
    assert "stable ordering is mandatory" in text.lower()
    assert "complete listing identity `(isin, exchange, code)`" in text


def test_contract_freezes_performance_budgets() -> None:
    text = _contract()
    for budget in (
        "`<= 750 ms`",
        "`<= 400 ms`",
        "`<= 200 ms`",
        "`<= 1000 ms`",
    ):
        assert budget in text
    assert "deterministic local PostgreSQL/Dash fixtures" in text
    assert "query count" in text
    assert "returned-row count" in text
    assert "response-body size" in text


def test_contract_prohibits_compute_and_unbounded_page_reads() -> None:
    text = _contract()
    for requirement in (
        "call `run_detail()` as its normal data source",
        "call the market gateway",
        "invoke financial computation",
        "deserialize an unbounded row collection",
        "all-pairs Bivariate payloads sent to the browser",
        "Redis, Celery, RQ, a new Compose worker, Node",
    ):
        assert requirement in text
    assert "Previous selection" in text
    assert "must never be combined" in text
