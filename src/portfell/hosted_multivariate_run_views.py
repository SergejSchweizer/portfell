"""Read-only views for project-scoped multivariate runs."""

from __future__ import annotations

from typing import cast

from portfell.hosted_api_errors import HostedApplicationError
from portfell.hosted_api_state import MultivariateRunRecord
from portfell.multivariate_run_view import candidate_row, multivariate_run_row
from portfell.table_io import JsonRow


class MultivariateRunViews:
    """Format persisted run records without owning their repository lifecycle."""

    def _require_run(self, user_id: str, run_id: str) -> MultivariateRunRecord:
        raise NotImplementedError

    def status(self, user_id: str, run_id: str) -> JsonRow:
        return multivariate_run_row(self._require_run(user_id, run_id))

    def summary(self, user_id: str, run_id: str) -> JsonRow:
        return dict(self._require_run(user_id, run_id).summary)

    def structure(self, user_id: str, run_id: str) -> JsonRow:
        return dict(self._require_run(user_id, run_id).structure)

    def candidates(self, user_id: str, run_id: str) -> JsonRow:
        return {"items": list(self._require_run(user_id, run_id).candidates)}

    def candidate_detail(self, user_id: str, run_id: str, candidate_id: str) -> JsonRow:
        candidate = candidate_row(self._require_run(user_id, run_id).candidates, candidate_id)
        if candidate is None:
            raise HostedApplicationError(404, "not_found")
        return candidate

    def risk_contributions(self, user_id: str, run_id: str, candidate_id: str | None) -> JsonRow:
        run = self._require_run(user_id, run_id)
        items = tuple(
            item
            for item in run.risk_contributions
            if candidate_id is None or item.get("candidate_id") == candidate_id
        )
        return {"items": list(items)}

    def income_evidence(self, user_id: str, run_id: str) -> JsonRow:
        return {"items": list(self._require_run(user_id, run_id).income_evidence)}

    def components(self, user_id: str, run_id: str, limit: int, offset: int) -> JsonRow:
        run = self._require_run(user_id, run_id)
        safe_limit, safe_offset = max(1, min(limit, 100)), max(0, offset)
        return {
            "items": list(run.components[safe_offset : safe_offset + safe_limit]),
            "total": len(run.components),
            "limit": safe_limit,
            "offset": safe_offset,
        }

    def validation(self, user_id: str, run_id: str) -> JsonRow:
        return {"items": list(self._require_run(user_id, run_id).validation)}

    def artifacts(self, user_id: str, run_id: str) -> JsonRow:
        return dict(self._require_run(user_id, run_id).artifacts)

    def performance(self, user_id: str, run_id: str) -> JsonRow:
        run = self._require_run(user_id, run_id)
        performance = run.artifacts.get("performance", {})
        return cast(JsonRow, performance) if isinstance(performance, dict) else {}
