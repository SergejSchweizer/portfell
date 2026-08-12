"""State records and repository container for the hosted API."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol
from uuid import UUID

from portfell.entitlements import InMemoryEntitlementStore, ProviderDownloadRun
from portfell.hosted_credentials import (
    CredentialStore,
    EodhdCredentialVault,
    InMemoryCredentialStore,
    KeyEncryptionKey,
)
from portfell.hosted_research_workflow import ResearchRun, UnivariateSelection
from portfell.hosted_workspace import LocalWorkspaceStore
from portfell.table_io import JsonRow

if TYPE_CHECKING:
    from portfell.shared_market_data import SharedMarketDataStore

DEFAULT_LOCAL_WORKSPACE_USER_ID = "00000000-0000-5000-8000-000000000001"


class UserOwnedRow(Protocol):
    """Protocol for rows that are scoped to one hosted API user."""

    @property
    def user_id(self) -> str:
        """User that owns the row."""
        ...


@dataclass(frozen=True)
class ApiUser:
    """A server-resolved API user."""

    user_id: str


class CurrentUserProvider(Protocol):
    """Resolve the request principal without browser-controlled identity input."""

    def current_user(self) -> ApiUser:
        """Return the server-owned user for the current request."""
        ...


@dataclass(frozen=True)
class ConfiguredUserProvider:
    """Resolve one server-configured principal without browser input."""

    user_id: str = DEFAULT_LOCAL_WORKSPACE_USER_ID

    def __post_init__(self) -> None:
        try:
            UUID(self.user_id)
        except ValueError as error:
            raise ValueError("local workspace user id must be a UUID") from error

    def current_user(self) -> ApiUser:
        """Return the configured server-side principal."""

        return ApiUser(user_id=self.user_id)


LocalWorkspaceUserProvider = ConfiguredUserProvider


@dataclass(frozen=True)
class ProjectRecord:
    """User-owned project record."""

    project_id: str
    user_id: str
    name: str


@dataclass(frozen=True)
class SelectionRecord:
    """User-owned selection record."""

    selection_id: str
    user_id: str
    project_id: str
    name: str
    member_ids: tuple[str, ...]
    metadata_builder_predicates: tuple[str, ...] = ()


@dataclass(frozen=True)
class AnalysisRecord:
    """User-owned analysis run record."""

    run_id: str
    user_id: str
    project_id: str
    selection_id: str
    logical_hash: str
    status: str
    metrics: tuple[JsonRow, ...]
    returns: tuple[JsonRow, ...]
    weights: tuple[JsonRow, ...]
    report: JsonRow


@dataclass(frozen=True)
class MultivariateRunRecord:
    """Project-owned persisted Multivariate run and API-ready result sections."""

    run_id: str
    user_id: str
    project_id: str
    bivariate_run_id: str
    input_snapshot_id: str
    logical_hash: str
    status: str
    phase: str
    completed_units: int
    total_units: int
    started_at_epoch: float
    settings: JsonRow
    summary: JsonRow
    structure: JsonRow
    candidates: tuple[JsonRow, ...]
    validation: tuple[JsonRow, ...]
    artifacts: JsonRow = field(default_factory=lambda: dict[str, Any]())
    components: tuple[JsonRow, ...] = ()
    risk_contributions: tuple[JsonRow, ...] = ()
    income_evidence: tuple[JsonRow, ...] = ()
    warnings: tuple[str, ...] = ()
    failure_reason: str | None = None


@dataclass
class HostedApiState:
    """In-memory hosted API repository set for deterministic tests and local dev."""

    credentials: CredentialStore = field(default_factory=InMemoryCredentialStore)
    credential_key_encryption_key: KeyEncryptionKey | None = field(
        default_factory=lambda: KeyEncryptionKey("dev-v1", b"0" * 32)
    )
    credential_fingerprint_secret: bytes = b"portfell-dev-fingerprint-secret"
    entitlements: InMemoryEntitlementStore = field(default_factory=InMemoryEntitlementStore)
    projects_by_id: dict[str, ProjectRecord] = field(
        default_factory=lambda: dict[str, ProjectRecord]()
    )
    selections_by_id: dict[str, SelectionRecord] = field(
        default_factory=lambda: dict[str, SelectionRecord]()
    )
    downloads_by_id: dict[str, ProviderDownloadRun] = field(
        default_factory=lambda: dict[str, ProviderDownloadRun]()
    )
    download_summaries_by_id: dict[str, JsonRow] = field(
        default_factory=lambda: dict[str, JsonRow]()
    )
    metadata_runs_by_id: dict[str, JsonRow] = field(default_factory=lambda: dict[str, JsonRow]())
    analyses_by_id: dict[str, AnalysisRecord] = field(
        default_factory=lambda: dict[str, AnalysisRecord]()
    )
    idempotency_refs: dict[tuple[str, str, str], str] = field(
        default_factory=lambda: dict[tuple[str, str, str], str]()
    )
    audit_events: list[JsonRow] = field(default_factory=lambda: list[JsonRow]())
    all_isins_rows: tuple[JsonRow, ...] = field(default_factory=tuple)
    univariate_statistics_rows: tuple[JsonRow, ...] = field(default_factory=tuple)
    metadata_revisions_by_user: dict[str, str] = field(default_factory=lambda: dict[str, str]())
    quote_rows_by_run_id: dict[str, tuple[JsonRow, ...]] = field(
        default_factory=lambda: dict[str, tuple[JsonRow, ...]]()
    )
    univariate_runs_by_id: dict[str, ResearchRun] = field(
        default_factory=lambda: dict[str, ResearchRun]()
    )
    univariate_selections_by_id: dict[str, UnivariateSelection] = field(
        default_factory=lambda: dict[str, UnivariateSelection]()
    )
    bivariate_runs_by_id: dict[str, ResearchRun] = field(
        default_factory=lambda: dict[str, ResearchRun]()
    )
    multivariate_runs_by_id: dict[str, MultivariateRunRecord] = field(
        default_factory=lambda: dict[str, MultivariateRunRecord]()
    )
    current_multivariate_run_by_project: dict[str, str] = field(
        default_factory=lambda: dict[str, str]()
    )
    quote_run_by_univariate_run_id: dict[str, str] = field(default_factory=lambda: dict[str, str]())
    current_metadata_selection_by_user: dict[str, str] = field(
        default_factory=lambda: dict[str, str]()
    )
    current_univariate_selection_by_user: dict[str, str] = field(
        default_factory=lambda: dict[str, str]()
    )
    univariate_selection_settings_by_project: dict[str, JsonRow] = field(
        default_factory=lambda: dict[str, JsonRow]()
    )
    current_project_id_by_user: dict[str, str] = field(default_factory=lambda: dict[str, str]())
    workspace_store: LocalWorkspaceStore | None = None
    shared_market_data_store: SharedMarketDataStore | None = None

    def credential_vault(self) -> EodhdCredentialVault:
        """Return the vault configured for this API state."""

        return EodhdCredentialVault(
            store=self.credentials,
            key_encryption_key=self.credential_key_encryption_key,
            fingerprint_secret=self.credential_fingerprint_secret,
        )
