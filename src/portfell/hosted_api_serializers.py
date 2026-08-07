"""Stable JSON serializers for hosted API values."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from portfell.entitlements import ProviderDownloadRun
from portfell.hosted_api_state import AnalysisRecord, ProjectRecord, SelectionRecord
from portfell.hosted_credentials import CredentialStatus
from portfell.hosted_research_workflow import FilterSelection, ResearchRun
from portfell.table_io import JsonRow


def credential_status_row(value: CredentialStatus) -> JsonRow:
    return {
        "credential_id": value.credential_id,
        "provider": value.provider,
        "status": value.status,
        "key_version": value.key_version,
        "masked_label": value.masked_label,
    }


def research_run_row(run: ResearchRun) -> JsonRow:
    percent = 100 if run.total == 0 else int(((run.completed + run.failed) / run.total) * 100)
    return {
        "run_id": run.run_id,
        "status": run.status,
        "total": run.total,
        "completed": run.completed,
        "failed": run.failed,
        "percent": percent,
    }


def filter_selection_row(selection: FilterSelection) -> JsonRow:
    selected_count = len(selection.rows)
    return {
        "selection_id": selection.selection_id,
        "source_run_id": selection.source_run_id,
        "input_count": selection.input_count,
        "selected_count": selected_count,
        "excluded_count": selection.input_count - selected_count,
        "predicates": [
            {
                "metric": predicate.field,
                "operator": predicate.operator,
                "value": float(predicate.expected),
            }
            for predicate in selection.predicates
        ],
    }


def univariate_metric_rows() -> list[JsonRow]:
    labels = {
        "quote_observation_count": ("Observations", "count"),
        "annualized_return": ("Annualized return", "ratio"),
        "annualized_volatility": ("Annualized volatility", "ratio"),
        "sharpe_ratio": ("Sharpe ratio", "ratio"),
        "max_drawdown": ("Maximum drawdown", "ratio"),
        "expected_shortfall": ("Expected shortfall", "ratio"),
    }
    return [
        {
            "metric": metric,
            "label": label,
            "unit": unit,
            "operators": ["=", "!=", ">", ">=", "<", "<="],
        }
        for metric, (label, unit) in labels.items()
    ]


def download_row(run: ProviderDownloadRun) -> JsonRow:
    return {
        "download_run_id": run.download_run_id,
        "provider": run.provider,
        "status": run.status,
        "observation_count": len(run.returned_observation_ids),
    }


def quote_run_row(run: ProviderDownloadRun, *, summary: Mapping[str, Any] | None = None) -> JsonRow:
    values = dict(summary or {})
    total = int(values.get("total", len(run.returned_observation_ids)))
    completed = int(values.get("completed", values.get("quote_successes", 0)))
    failed = int(values.get("failed", values.get("quote_errors", 0)))
    percent = int(values.get("percent", 100 if run.status == "succeeded" else 0))
    return {
        **download_row(run),
        "kind": "load-data",
        "total": total,
        "completed": completed,
        "failed": failed,
        "percent": percent,
        "progress": percent,
        "started_at": float(values.get("started_at", 0)),
        "quote_errors": int(values.get("quote_errors", 0)),
        "quote_successes": int(values.get("quote_successes", 0)),
        "raw_dataset_errors": int(values.get("raw_dataset_errors", 0)),
        "raw_dataset_successes": int(values.get("raw_dataset_successes", 0)),
        "run_id": run.download_run_id,
        "selected_listing_count": int(
            values.get("selected_listing_count", len(run.returned_observation_ids))
        ),
        "selected_count": len(run.returned_observation_ids),
        "silver_quote_rows": int(values.get("silver_quote_rows", 0)),
    }


def metadata_fetch_row(run: Mapping[str, Any]) -> JsonRow:
    return {key: value for key, value in run.items() if key != "user_id"}


def project_row(project: ProjectRecord) -> JsonRow:
    return {"project_id": project.project_id, "name": project.name}


def selection_row(selection: SelectionRecord) -> JsonRow:
    return {
        "selection_id": selection.selection_id,
        "project_id": selection.project_id,
        "name": selection.name,
        "member_ids": list(selection.member_ids),
    }


def analysis_row(analysis: AnalysisRecord) -> JsonRow:
    return {
        "run_id": analysis.run_id,
        "project_id": analysis.project_id,
        "selection_id": analysis.selection_id,
        "status": analysis.status,
    }
