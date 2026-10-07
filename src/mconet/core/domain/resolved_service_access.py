"""Immutable service access values produced by configuration resolution."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import cast

from mconet.core.domain.authorization import Authorization
from mconet.core.domain.extensions import Extensions
from mconet.core.domain.headers import Headers
from mconet.core.domain.json_value import JsonValue
from mconet.core.domain.open_identifier import OpenIdentifier
from mconet.core.domain.query_parameters import QueryParameters
from mconet.core.domain.uri import UriValue


@dataclass(frozen=True, slots=True)
class ResolvedServiceAccess:
    """Carry the complete access configuration selected for one interaction.

    Every field is explicit so execution never receives unresolved inheritance
    or omission semantics. Endpoint and provider context may legitimately remain
    absent, but authorization must be a concrete implementation, including an
    explicit no-authorization implementation when credentials are unnecessary.
    """

    endpoint: UriValue | None
    """Optional resolved service endpoint with its URI-reference classification."""

    authorization: Authorization
    """Concrete opaque authorization selected for this interaction."""

    headers: Headers
    """Ordered resolved non-sensitive custom headers."""

    query: QueryParameters
    """Ordered resolved non-sensitive custom query parameters."""

    api_version: str | None
    """Optional resolved provider API version context."""

    project_id: str | None
    """Optional resolved provider project context."""

    tenant_id: str | None
    """Optional resolved provider tenant context."""

    extensions: Extensions
    """Read-only top-level snapshot of resolved portable extension values."""

    def __post_init__(self) -> None:
        """Require complete field shapes and detach extension membership."""
        endpoint = cast(object, self.endpoint)
        authorization = cast(object, self.authorization)
        headers = cast(object, self.headers)
        query = cast(object, self.query)

        # Preserve an explicitly absent endpoint while requiring the nominal URI
        # value whenever resolution selected one. URI semantics stay with the
        # source validator and resolver rather than being repeated here.
        if endpoint is not None and not isinstance(endpoint, UriValue):
            raise TypeError(
                "ResolvedServiceAccess endpoint must be a UriValue or None."
            )

        # None no longer represents inherited or missing authorization after
        # resolution. Structural implementations remain open, but their handler
        # discriminator must use the shared nominal identifier value.
        if not isinstance(authorization, Authorization):
            raise TypeError(
                "ResolvedServiceAccess authorization must implement Authorization."
            )
        authorization_kind = cast(object, authorization.kind)
        if not isinstance(authorization_kind, OpenIdentifier):
            raise TypeError(
                "ResolvedServiceAccess authorization kind must be an OpenIdentifier."
            )

        # Reuse the ordered immutable collection values so duplicate headers and
        # query parameters retain their exact resolution order without copying.
        if not isinstance(headers, Headers):
            raise TypeError("ResolvedServiceAccess headers must be Headers.")
        if not isinstance(query, QueryParameters):
            raise TypeError("ResolvedServiceAccess query must be QueryParameters.")

        # Provider context is opaque text. Empty strings and provider-specific
        # syntax remain resolver policy rather than generic storage invariants.
        for field_name, value in (
            ("api_version", cast(object, self.api_version)),
            ("project_id", cast(object, self.project_id)),
            ("tenant_id", cast(object, self.tenant_id)),
        ):
            if value is not None and not isinstance(value, str):
                raise TypeError(
                    f"ResolvedServiceAccess {field_name} must be a string or None."
                )

        # Freeze top-level extension membership so the resolved snapshot cannot
        # be changed through a caller-owned source mapping during execution.
        object.__setattr__(self, "extensions", _snapshot_extensions(self.extensions))


def _snapshot_extensions(value: object) -> Extensions:
    """Copy string-keyed resolved extensions into read-only top-level storage."""
    # The public Extensions type is a mapping of JSON object member names; reject
    # sequences, scalars, and non-string keys before creating the snapshot.
    if not isinstance(value, Mapping):
        raise TypeError("ResolvedServiceAccess extensions must be a mapping.")
    source = cast(Mapping[object, object], value)
    if any(not isinstance(key, str) for key in source):
        raise TypeError("ResolvedServiceAccess extensions keys must be strings.")

    # Nested JSON values retain identity and are validated before resolution;
    # only membership needs detaching to make this interaction snapshot stable.
    snapshot = dict(cast(Mapping[str, JsonValue], source))
    return MappingProxyType(snapshot)
