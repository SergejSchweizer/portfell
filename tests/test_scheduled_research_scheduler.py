from datetime import UTC, datetime

from portfell.scheduled_research.scheduler import (
    CRON_EXPRESSION,
    CRON_TZ,
    ProjectTerminal,
    coordinate_cycle,
    next_sunday_run,
)


def test_schedule_contract_and_next_run_use_vienna_sunday_0900() -> None:
    assert CRON_TZ == "Europe/Vienna"
    assert CRON_EXPRESSION == "0 9 * * 0"
    next_run = next_sunday_run(datetime(2026, 8, 20, 7, 0, tzinfo=UTC))
    assert next_run.isoformat() == "2026-08-23T09:00:00+02:00"


def test_cycle_refreshes_once_and_processes_projects_in_stable_unique_order() -> None:
    refresh_calls = 0
    project_calls: list[tuple[str, str]] = []

    def refresh_market() -> str:
        nonlocal refresh_calls
        refresh_calls += 1
        return "market-r1"

    def run_project(project_slug: str, revision: str) -> ProjectTerminal:
        project_calls.append((project_slug, revision))
        return ProjectTerminal(project_slug, True, reused_runs=1, new_runs=2)

    result = coordinate_cycle(
        cycle_date="2026-08-23",
        project_slugs=("beta", "alpha", "beta"),
        refresh_market=refresh_market,
        run_project=run_project,
    )

    assert refresh_calls == 1
    assert project_calls == [("alpha", "market-r1"), ("beta", "market-r1")]
    assert result.project_count == 2
    assert result.successful_projects == 2
    assert result.reused_runs == 2
    assert result.new_runs == 4


def test_project_failure_is_isolated_and_summary_is_count_only() -> None:
    def run_project(project_slug: str, revision: str) -> ProjectTerminal:
        assert revision == "market-r1"
        if project_slug == "alpha":
            raise RuntimeError("secret failure payload")
        return ProjectTerminal(project_slug, True, reused_runs=0, new_runs=3)

    result = coordinate_cycle(
        cycle_date="2026-08-23",
        project_slugs=("alpha", "beta"),
        refresh_market=lambda: "market-r1",
        run_project=run_project,
    )

    assert result.failed_projects == 1
    assert result.successful_projects == 1
    assert "secret" not in repr(result.public_dict()).lower()
