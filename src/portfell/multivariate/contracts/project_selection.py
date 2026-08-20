"""Project-scoped immutable current-selection contract."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from portfell.multivariate.contracts.common import ListingIdentity
from portfell.multivariate.contracts.serialization import canonical_json


@dataclass(frozen=True, slots=True)
class ProjectSelection:
    project_slug: str
    upstream_revision: str
    listings: tuple[ListingIdentity, ...]

    def __post_init__(self) -> None:
        if not self.project_slug or not self.upstream_revision:
            raise ValueError("project_slug and upstream_revision are required")
        if len(set(self.listings)) != len(self.listings):
            raise ValueError("project selection cannot contain duplicate listings")

    @property
    def selection_revision(self) -> str:
        ordered = tuple(sorted(self.listings))
        return hashlib.sha256(
            canonical_json(
                {
                    "project_slug": self.project_slug,
                    "upstream_revision": self.upstream_revision,
                    "listings": ordered,
                }
            ).encode()
        ).hexdigest()
