from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from portfell.hosted_metadata_refresh_job_repository import ClaimedMetadataRefresh
from portfell.hosted_metadata_refresh_worker import MetadataRefreshWorker
from portfell.hosted_metadata_repository import MetadataRun
from portfell.shared_metadata_catalog import SharedMetadataCatalog


class Jobs:
    def __init__(self, claim: ClaimedMetadataRefresh | None) -> None:
        self.claim_value = claim
        self.completed: list[bool] = []

    def claim(self) -> ClaimedMetadataRefresh | None:
        claim, self.claim_value = self.claim_value, None
        return claim

    def complete(self, claim: ClaimedMetadataRefresh, *, succeeded: bool) -> None:
        del claim
        self.completed.append(succeeded)


class Runs:
    def __init__(self, run: MetadataRun) -> None:
        self.run = run
        self.revisions: list[str] = []

    def status(self, *, user_id: str, run_id: str) -> MetadataRun | None:
        return (
            self.run if self.run.user_id == user_id and self.run.metadata_run_id == run_id else None
        )

    def update(self, run: MetadataRun) -> MetadataRun:
        self.run = run
        return run

    def set_revision(self, *, user_id: str, revision_id: str) -> None:
        assert user_id == self.run.user_id
        self.revisions.append(revision_id)


class Client:
    def __init__(self, *, fails: bool = False) -> None:
        self.fails = fails

    def get_json(self, path: str, params: Mapping[str, str | int | float] | None = None) -> object:
        del params
        if self.fails:
            raise RuntimeError("provider unavailable")
        if path == "/exchanges-list/":
            return [{"Code": "XETRA"}]
        if path == "/exchange-symbol-list/XETRA":
            return [
                {
                    "Code": "ALPHA",
                    "Exchange": "XETRA",
                    "Name": "Alpha ETF",
                    "Type": "ETF",
                    "Country": "IE",
                    "Currency": "EUR",
                    "Isin": "IE00ALPHA001",
                }
            ]
        raise AssertionError(path)


def _run() -> MetadataRun:
    return MetadataRun(
        "00000000-0000-0000-0000-000000000001",
        "00000000-0000-0000-0000-000000000002",
        "running",
        0,
        0,
        0,
        0,
        {},
    )


def test_metadata_refresh_worker_publishes_the_shared_catalog(tmp_path: Path) -> None:
    run = _run()
    claim = ClaimedMetadataRefresh(
        run.metadata_run_id, run.user_id, "00000000-0000-0000-0000-000000000003"
    )
    jobs = Jobs(claim)
    runs = Runs(run)
    catalog = SharedMetadataCatalog(tmp_path)
    worker = MetadataRefreshWorker(
        jobs=jobs, runs=runs, catalog=catalog, client=Client(), cpu_count=lambda: 1
    )  # type: ignore[arg-type]

    result = worker.run_once()

    assert result.claimed and result.succeeded
    assert jobs.completed == [True]
    assert runs.run.status == "succeeded"
    assert runs.run.summary["row_count"] == 1
    assert catalog.read()[0]["isin"] == "IE00ALPHA001"


def test_metadata_refresh_worker_records_a_safe_failed_run(tmp_path: Path) -> None:
    run = _run()
    claim = ClaimedMetadataRefresh(
        run.metadata_run_id, run.user_id, "00000000-0000-0000-0000-000000000003"
    )
    jobs = Jobs(claim)
    runs = Runs(run)
    worker = MetadataRefreshWorker(
        jobs=jobs,
        runs=runs,
        catalog=SharedMetadataCatalog(tmp_path),
        client=Client(fails=True),
        cpu_count=lambda: 1,
    )  # type: ignore[arg-type]

    result = worker.run_once()

    assert result.claimed and not result.succeeded
    assert jobs.completed == [False]
    assert runs.run.status == "failed"
    assert runs.run.summary["error_code"] == "eodhd_metadata_unavailable"


def test_metadata_refresh_worker_bounds_default_concurrency(tmp_path: Path, monkeypatch) -> None:
    run = _run()
    claim = ClaimedMetadataRefresh(
        run.metadata_run_id, run.user_id, "00000000-0000-0000-0000-000000000003"
    )
    seen: dict[str, int] = {}

    def fetch(client: Client, *, concurrency: int, on_progress: object) -> object:
        del client, on_progress
        seen["concurrency"] = concurrency
        return type(
            "Result", (), {"rows": (), "requested_exchanges": (), "skipped_exchanges": ()}
        )()

    monkeypatch.setattr("portfell.hosted_metadata_refresh_worker.fetch_all_metadata", fetch)
    worker = MetadataRefreshWorker(
        jobs=Jobs(claim),
        runs=Runs(run),
        catalog=SharedMetadataCatalog(tmp_path),
        client=Client(),
        cpu_count=lambda: 32,
    )  # type: ignore[arg-type]

    assert worker.run_once().succeeded
    assert seen["concurrency"] == 4
