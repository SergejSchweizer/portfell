"""Request contracts for the hosted FastAPI boundary."""

from __future__ import annotations

from pydantic import BaseModel, Field

from portfell.table_io import JsonRow


class CredentialSetRequest(BaseModel):
    """Request to set or replace a provider credential."""

    provider_key: str = Field(min_length=1, max_length=4096)


class DownloadRequest(BaseModel):
    """Request to plan or run a user-key-backed download."""

    symbols: list[str] = Field(default_factory=list, max_length=1000)


class ProjectCreateRequest(BaseModel):
    """Request to create one user-owned project."""

    name: str = Field(min_length=1, max_length=120)


class CurrentProjectRequest(BaseModel):
    """Request to select the current local-workspace project."""

    project_id: str = Field(min_length=1, max_length=160)


class MetadataBuilderProjectRequest(BaseModel):
    """Request to create one project from metadata-builder criteria."""

    exchange: str = Field(default="", max_length=80)
    name: str = Field(default="", max_length=240)
    instrument_type: str = Field(default="", max_length=80)
    country: str = Field(default="", max_length=80)
    currency: str = Field(default="", max_length=80)


class SelectionCreateRequest(BaseModel):
    """Request to persist one user-owned selection."""

    project_id: str
    name: str = Field(min_length=1, max_length=120)
    member_ids: list[str] = Field(default_factory=list, min_length=1, max_length=1000)


class AnalysisCreateRequest(BaseModel):
    """Request to submit one analysis over an authorized selection."""

    project_id: str
    selection_id: str
    settings: JsonRow = Field(default_factory=dict)


class UnivariateRunRequest(BaseModel):
    """Immutable inputs for one univariate statistics run."""

    metadata_selection_id: str
    quote_run_id: str


class UnivariateSelectionRangeRequest(BaseModel):
    minimum: float
    maximum: float


class UnivariateSelectionSettingsRequest(BaseModel):
    """Project-scoped UI selections used to narrow the univariate universe."""

    dividend_frequencies: list[str] = Field(default_factory=list, max_length=6)
    statistic_labels: dict[str, list[str]] = Field(default_factory=dict, max_length=20)
    statistic_ranges: dict[str, list[UnivariateSelectionRangeRequest]] = Field(
        default_factory=dict, max_length=20
    )


class NumericalPredicateRequest(BaseModel):
    """One numerical filter predicate."""

    metric: str
    operator: str
    value: float


class UnivariateSelectionRequest(BaseModel):
    """Predicates applied to one user-owned univariate run."""

    source_run_id: str
    selection_name: str | None = None
    predicates: list[NumericalPredicateRequest] = Field(min_length=1, max_length=100)


class BivariateSelectionRequest(BaseModel):
    """Source selection for pair planning and execution."""

    univariate_selection_id: str


class MultivariateRunRequest(BaseModel):
    """Pinned Bivariate dependency and bounded project settings."""

    project_id: str = Field(min_length=1, max_length=160)
    bivariate_run_id: str = Field(min_length=1, max_length=160)
    settings: JsonRow = Field(default_factory=dict)


class LoadSelectedIsinsRequest(BaseModel):
    """Request to load quote data for one user-owned project selection."""

    project_id: str | None = None
    metadata_selection_id: str | None = None
