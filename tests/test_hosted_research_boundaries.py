from __future__ import annotations

from dataclasses import dataclass

from portfell.entitlements import ProviderDownloadRun
from portfell.hosted_api_state import HostedApiState, SelectionRecord
from portfell.hosted_research_ports import ResearchDataset, UnivariateProgress
from portfell.hosted_research_repository import HostedResearchRepository
from portfell.hosted_univariate_service import UnivariateResearchService
from portfell.table_io import JsonRow


@dataclass
class FakeResearchData:
    univariate_rows: tuple[JsonRow, ...]
    selected_calls: list[tuple[tuple[str, ...], ResearchDataset]]

    def selected_rows(
        self, member_ids: tuple[str, ...], *, dataset: ResearchDataset
    ) -> tuple[JsonRow, ...]:
        self.selected_calls.append((member_ids, dataset))
        return ()

    def build_univariate_rows(
        self,
        member_ids: tuple[str, ...],
        *,
        on_progress: UnivariateProgress | None = None,
    ) -> tuple[JsonRow, ...]:
        if on_progress is not None:
            for completed, _member_id in enumerate(member_ids, start=1):
                on_progress(completed)
        return self.univariate_rows


@dataclass
class RecordingPersistence:
    calls: int = 0

    def persist(self) -> None:
        self.calls += 1


def test_univariate_service_uses_injected_data_and_persistence_ports() -> None:
    member_id = "IE1:XETRA:AAA"
    selection = SelectionRecord("selection-1", "user-a", "project-1", "UCITS", (member_id,))
    quote_run = ProviderDownloadRun(
        "quote-1", "user-a", "credential-1", "eodhd", "succeeded", (), "hash-1"
    )
    state = HostedApiState(
        selections_by_id={selection.selection_id: selection},
        downloads_by_id={quote_run.download_run_id: quote_run},
    )
    data = FakeResearchData(
        univariate_rows=(
            {
                "isin": "IE1",
                "exchange": "XETRA",
                "code": "AAA",
                "observation_count": 100,
            },
        ),
        selected_calls=[],
    )
    persistence = RecordingPersistence()
    service = UnivariateResearchService(HostedResearchRepository(state), data, persistence)

    started = service.start("user-a", selection.selection_id, quote_run.download_run_id)
    service.complete("user-a", selection.selection_id, quote_run.download_run_id)

    completed = state.univariate_runs_by_id[str(started["run_id"])]
    assert completed.status == "complete"
    assert completed.rows == data.univariate_rows
    assert state.current_filter_selection_by_user["user-a"] in state.filter_selections_by_id
    assert data.selected_calls == []
    assert persistence.calls == 1
