"""Shadow comparison manifest for the frozen 14 risk-model configurations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from concurrent.futures import Executor
from dataclasses import dataclass, replace
from typing import Any

from portfell.contract_versioning import ContractVersion
from portfell.income import IncomeEvidence
from portfell.multivariate_candidates import PortfolioCandidate, build_candidate_set
from portfell.multivariate_inputs import MultivariateInputSnapshot, MultivariateListingKey
from portfell.multivariate_risk_model import build_multivariate_risk_model
from portfell.multivariate_risk_spec import (
    EWMA_094,
    LW_FULL,
    LW_ROLLING_252,
)
from portfell.multivariate_selection_ranking import (
    build_configuration_scorecards,
    rank_configuration_scorecards,
)
from portfell.multivariate_validation import (
    DEFAULT_WALK_FORWARD_POLICY,
    WalkForwardPolicy,
    _walk_forward_starts,  # pyright: ignore[reportPrivateUsage]
    validate_candidates,
    walk_forward_validation_row,
)
from portfell.selection_v2_contract import SELECTION_V2_CONFIGURATIONS, SELECTION_V2_POLICY

RISK_MODEL_COMPARISON_CONTRACT = ContractVersion("multivariate.risk_model_comparison", 2)
COMPARISON_SPECS = (LW_FULL, LW_ROLLING_252, EWMA_094)
COMPARISON_WALK_FORWARD_POLICY = WalkForwardPolicy(
    minimum_training_observations=252,
    test_window_observations=21,
    maximum_refit_count=8,
    minimum_completed_splits=2,
)
COMPARISON_METHODS = {
    "equal_weight": ("LW_FULL",),
    "inverse_volatility": ("LW_FULL", "LW_ROLLING_252", "EWMA_094"),
    "minimum_variance": ("LW_FULL", "LW_ROLLING_252", "EWMA_094"),
    "equal_risk_contribution": ("LW_FULL", "LW_ROLLING_252", "EWMA_094"),
    "hierarchical_risk_parity": ("LW_FULL", "LW_ROLLING_252", "EWMA_094"),
    "minimum_cvar": ("LW_FULL",),
}


@dataclass(frozen=True)
class SplitRiskModelBundle:
    """The three training-only risk-model fits shared by one OOS split."""

    split_index: int
    train_start: str | None
    train_end: str | None
    test_start: str | None
    test_end: str | None
    models: tuple[tuple[str, Any], ...]

    def model(self, spec_key: str) -> Any:
        return dict(self.models)[spec_key]

    def to_rows(self) -> tuple[dict[str, Any], ...]:
        return tuple(
            {
                "split_index": self.split_index,
                "train_start": self.train_start,
                "train_end": self.train_end,
                "test_start": self.test_start,
                "test_end": self.test_end,
                "spec_key": spec_key,
                "spec_id": model.spec_id,
                "risk_model_id": model.risk_model_id,
                "fit_calendar_id": model.fit_calendar_id,
                "status": "available" if model.available else "unavailable",
                "reason": model.availability_reasons[0] if model.availability_reasons else None,
                "observation_count": model.observation_count,
            }
            for spec_key, model in self.models
        )


def build_risk_model_comparison(
    *,
    snapshot: MultivariateInputSnapshot,
    return_rows: Sequence[Mapping[str, Any]],
    income: Mapping[MultivariateListingKey, IncomeEvidence],
    executor: Executor | None = None,
) -> dict[str, Any]:
    """Build deterministic common-OOS comparison and current-sample evidence."""
    models: dict[str, Any] = {}
    for spec in COMPARISON_SPECS:
        models[spec.spec_key] = build_multivariate_risk_model(
            snapshot=snapshot, return_rows=return_rows, spec=spec
        )
    definitions: list[dict[str, Any]] = [item.to_row() for item in SELECTION_V2_CONFIGURATIONS]
    evidence: list[dict[str, Any]] = []
    split_evidence: list[dict[str, Any]] = []
    dates = _common_dates(return_rows, snapshot.listing_keys)
    starts = _walk_forward_starts(dates, COMPARISON_WALK_FORWARD_POLICY)
    split_bundles = build_split_risk_model_bundles(
        snapshot=snapshot, return_rows=return_rows, dates=dates, starts=starts
    )
    split_families = build_split_candidate_families(
        snapshot=snapshot,
        return_rows=return_rows,
        income=income,
        bundles=split_bundles,
        executor=executor,
    )
    common_validation = build_common_oos_validation(
        return_rows=return_rows,
        families=split_families,
        executor=executor,
    )
    common_validation_rows = [walk_forward_validation_row(item) for item in common_validation]
    configuration_scorecards = build_configuration_scorecards(
        validation_rows=common_validation_rows,
        required_split_count=COMPARISON_WALK_FORWARD_POLICY.minimum_completed_splits,
    )
    for method, spec_keys in COMPARISON_METHODS.items():
        for spec_key in spec_keys:
            spec = next(item for item in COMPARISON_SPECS if item.spec_key == spec_key)
            model = models[spec_key]
            candidates = build_candidate_set(
                snapshot=snapshot,
                risk_model=model,
                return_rows=return_rows,
                income=income,
                executor=executor,
            )
            evidence.extend(
                {
                    "method": candidate.method,
                    "spec_key": spec.spec_key,
                    "spec_id": spec.spec_id,
                    "candidate_id": candidate.candidate_id,
                    "candidate_configuration_id": candidate.candidate_configuration_id,
                    "status": candidate.status,
                    "reason": candidate.reasons[0] if candidate.reasons else None,
                }
                for candidate in candidates
                if candidate.method == method
            )
            for bundle in split_bundles:
                split_model = bundle.model(spec_key)
                split_evidence.append(
                    {
                        "split_index": bundle.split_index,
                        "train_start": bundle.train_start,
                        "train_end": bundle.train_end,
                        "test_start": bundle.test_start,
                        "test_end": bundle.test_end,
                        "method": method,
                        "spec_key": spec.spec_key,
                        "spec_id": spec.spec_id,
                        "risk_model_id": split_model.risk_model_id,
                        "fit_calendar_id": split_model.fit_calendar_id,
                        "status": "scheduled" if split_model.available else "unavailable",
                        "reason": split_model.availability_reasons[0]
                        if split_model.availability_reasons
                        else None,
                    }
                )
    return {
        "contract_version": RISK_MODEL_COMPARISON_CONTRACT.qualified_name,
        "selection_v2_policy": SELECTION_V2_POLICY.to_row(),
        "selection_v2_policy_fingerprint": SELECTION_V2_POLICY.fingerprint,
        "configuration_count": len(definitions),
        "configurations": definitions,
        "full_sample_evidence": evidence,
        "common_split_count": len(starts),
        "common_split_evidence": split_evidence,
        "split_risk_model_bundles": [row for bundle in split_bundles for row in bundle.to_rows()],
        "split_candidate_families": [row for family in split_families for row in family.to_rows()],
        "common_oos_validation": [row for row in common_validation_rows],
        "configuration_scorecards": [card.to_row() for card in configuration_scorecards],
        "configuration_rankings": {
            objective: list(
                rank_configuration_scorecards(configuration_scorecards, objective=objective)
            )
            for objective in ("return_risk", "return_drawdown", "minimum_risk")
        },
        "risk_models": {
            key: {
                "risk_model_id": model.risk_model_id,
                "fit_calendar_id": model.fit_calendar_id,
                "status": "available" if model.available else "unavailable",
            }
            for key, model in models.items()
        },
    }


def build_split_risk_model_bundles(
    *,
    snapshot: MultivariateInputSnapshot,
    return_rows: Sequence[Mapping[str, Any]],
    dates: Sequence[str] | None = None,
    starts: Sequence[int] | None = None,
) -> tuple[SplitRiskModelBundle, ...]:
    """Fit each risk specification once per split using training rows only.

    The tuple is ordered by split and canonical specification order.  An
    unavailable fit remains an explicit artifact rather than being dropped.
    """
    common_dates = (
        tuple(dates) if dates is not None else _common_dates(return_rows, snapshot.listing_keys)
    )
    split_starts = (
        tuple(starts)
        if starts is not None
        else _walk_forward_starts(common_dates, COMPARISON_WALK_FORWARD_POLICY)
    )
    bundles: list[SplitRiskModelBundle] = []
    for split_index, start in enumerate(split_starts):
        train_dates = set(common_dates[:start])
        training_rows = tuple(row for row in return_rows if str(row.get("date", "")) in train_dates)
        test_end_index = min(
            len(common_dates) - 1,
            start + DEFAULT_WALK_FORWARD_POLICY.test_window_observations - 1,
        )
        models = tuple(
            (
                spec.spec_key,
                build_multivariate_risk_model(
                    snapshot=snapshot, return_rows=training_rows, spec=spec
                ),
            )
            for spec in COMPARISON_SPECS
        )
        bundles.append(
            SplitRiskModelBundle(
                split_index=split_index,
                train_start=common_dates[0] if train_dates else None,
                train_end=common_dates[start - 1] if start else None,
                test_start=common_dates[start] if start < len(common_dates) else None,
                test_end=common_dates[test_end_index] if common_dates else None,
                models=models,
            )
        )
    return tuple(bundles)


@dataclass(frozen=True)
class SplitCandidateFamily:
    """Exactly one candidate slot for every canonical config on a split."""

    split_index: int
    train_start: str | None
    train_end: str | None
    test_start: str | None
    test_end: str | None
    candidates: tuple[PortfolioCandidate, ...]

    def to_rows(self) -> tuple[dict[str, Any], ...]:
        return tuple(
            {
                "split_index": self.split_index,
                "train_start": self.train_start,
                "train_end": self.train_end,
                "test_start": self.test_start,
                "test_end": self.test_end,
                "configuration_id": candidate.candidate_configuration_id,
                "method": candidate.method,
                "spec_key": candidate.risk_model_spec_key,
                "spec_id": candidate.risk_model_spec_id,
                "candidate_id": candidate.candidate_id,
                "risk_model_id": candidate.risk_model_id,
                "fit_calendar_id": candidate.fit_calendar_id,
                "status": candidate.status,
                "reason": candidate.reasons[0] if candidate.reasons else None,
            }
            for candidate in self.candidates
        )


@dataclass(frozen=True)
class CurrentSampleCandidateFamily:
    """The descriptive full-sample 14-configuration family."""

    risk_models: tuple[tuple[str, Any], ...]
    candidates: tuple[PortfolioCandidate, ...]

    def model(self, spec_key: str) -> Any:
        return dict(self.risk_models)[spec_key]

    def to_rows(self) -> tuple[dict[str, Any], ...]:
        return tuple(
            {
                "configuration_id": candidate.candidate_configuration_id,
                "method": candidate.method,
                "spec_key": candidate.risk_model_spec_key,
                "spec_id": candidate.risk_model_spec_id,
                "candidate_id": candidate.candidate_id,
                "risk_model_id": candidate.risk_model_id,
                "fit_calendar_id": candidate.fit_calendar_id,
                "status": candidate.status,
                "reason": candidate.reasons[0] if candidate.reasons else None,
                "evidence_role": "descriptive",
            }
            for candidate in self.candidates
        )


def build_split_candidate_families(
    *,
    snapshot: MultivariateInputSnapshot,
    return_rows: Sequence[Mapping[str, Any]],
    income: Mapping[MultivariateListingKey, IncomeEvidence],
    bundles: Sequence[SplitRiskModelBundle],
    executor: Executor | None = None,
) -> tuple[SplitCandidateFamily, ...]:
    """Build the 14 canonical candidate slots from shared split-local fits."""
    families: list[SplitCandidateFamily] = []
    for bundle in bundles:
        candidates: list[PortfolioCandidate] = []
        split_return_rows = tuple(
            row
            for row in return_rows
            if bundle.train_end is None or str(row.get("date", "")) <= bundle.train_end
        )
        for configuration in SELECTION_V2_CONFIGURATIONS:
            risk_model = bundle.model(configuration.risk_model_spec.spec_key)
            built = build_candidate_set(
                snapshot=snapshot,
                risk_model=risk_model,
                return_rows=split_return_rows,
                income=income,
                executor=executor,
                methods=(configuration.method,),
            )
            if len(built) != 1:
                raise RuntimeError("split_candidate_family_slot_count_mismatch")
            candidates.append(
                replace(built[0], candidate_configuration_id=configuration.configuration_id)
            )
        families.append(
            SplitCandidateFamily(
                split_index=bundle.split_index,
                train_start=bundle.train_start,
                train_end=bundle.train_end,
                test_start=bundle.test_start,
                test_end=bundle.test_end,
                candidates=tuple(candidates),
            )
        )
    return tuple(families)


def build_common_oos_validation(
    *,
    return_rows: Sequence[Mapping[str, Any]],
    families: Sequence[SplitCandidateFamily],
    executor: Executor | None = None,
) -> tuple[Any, ...]:
    """Measure every split-local candidate on shared 21-observation windows."""
    if not families:
        return ()
    return validate_candidates(
        candidates=families[0].candidates,
        return_rows=return_rows,
        policy=COMPARISON_WALK_FORWARD_POLICY,
        precomputed_candidates=tuple(family.candidates for family in families),
        executor=executor,
    )


def build_current_sample_candidate_family(
    *,
    snapshot: MultivariateInputSnapshot,
    return_rows: Sequence[Mapping[str, Any]],
    income: Mapping[MultivariateListingKey, IncomeEvidence],
    executor: Executor | None = None,
) -> CurrentSampleCandidateFamily:
    """Fit at most three current-sample risk models and materialize 14 slots."""
    models = tuple(
        (
            spec.spec_key,
            build_multivariate_risk_model(snapshot=snapshot, return_rows=return_rows, spec=spec),
        )
        for spec in COMPARISON_SPECS
    )
    candidates: list[PortfolioCandidate] = []
    for configuration in SELECTION_V2_CONFIGURATIONS:
        built = build_candidate_set(
            snapshot=snapshot,
            risk_model=dict(models)[configuration.risk_model_spec.spec_key],
            return_rows=return_rows,
            income=income,
            executor=executor,
            methods=(configuration.method,),
        )
        if len(built) != 1:
            raise RuntimeError("current_sample_family_slot_count_mismatch")
        candidates.append(
            replace(built[0], candidate_configuration_id=configuration.configuration_id)
        )
    return CurrentSampleCandidateFamily(risk_models=models, candidates=tuple(candidates))


__all__ = [
    "COMPARISON_METHODS",
    "COMPARISON_SPECS",
    "COMPARISON_WALK_FORWARD_POLICY",
    "RISK_MODEL_COMPARISON_CONTRACT",
    "SplitRiskModelBundle",
    "SplitCandidateFamily",
    "CurrentSampleCandidateFamily",
    "build_risk_model_comparison",
    "build_split_candidate_families",
    "build_common_oos_validation",
    "build_current_sample_candidate_family",
    "build_split_risk_model_bundles",
]


def _common_dates(
    rows: Sequence[Mapping[str, Any]], listings: Sequence[MultivariateListingKey]
) -> tuple[str, ...]:
    indexed: dict[MultivariateListingKey, set[str]] = {key: set() for key in listings}
    for row in rows:
        key = MultivariateListingKey.from_row(row)
        if key in indexed:
            indexed[key].add(str(row.get("date", "")))
    if not indexed:
        return ()
    available = tuple(indexed.values())
    common: set[str] = set(available[0])
    for dates in available[1:]:
        common.intersection_update(dates)
    return tuple(sorted(item for item in common if item))
