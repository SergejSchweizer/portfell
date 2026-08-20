"""Multivariate logical-run identity and frozen progress phases."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum

from portfell.multivariate.contracts.serialization import canonical_json
from portfell.multivariate.contracts.settings import MultivariateOptimizationSettings


class MultivariateProgressPhase(StrEnum):
    SELECT_UNIVERSE = "select_universe"
    ESTIMATE_RISK_MODELS = "estimate_risk_models"
    BUILD_CANDIDATES = "build_candidates"
    WALK_FORWARD = "walk_forward"
    SELECT_WINNER = "select_winner"
    FINAL_REFIT = "final_refit"
    PUBLISH_DECISIONS = "publish_decisions"


PROGRESS_PHASE_ORDER: tuple[MultivariateProgressPhase, ...] = tuple(MultivariateProgressPhase)


@dataclass(frozen=True, slots=True)
class MultivariateRunIdentity:
    project_slug: str
    bivariate_revision: str
    settings: MultivariateOptimizationSettings
    settings_version: str
    algorithm_version: str

    def __post_init__(self) -> None:
        if not all((self.project_slug, self.bivariate_revision, self.settings_version, self.algorithm_version)):
            raise ValueError("run identity fields cannot be empty")

    @property
    def logical_run_id(self) -> str:
        payload = canonical_json(
            {
                "project_slug": self.project_slug,
                "bivariate_revision": self.bivariate_revision,
                "settings": self.settings,
                "settings_version": self.settings_version,
                "algorithm_version": self.algorithm_version,
            }
        ).encode()
        return hashlib.sha256(payload).hexdigest()
