"""Open structural contract for model service access configuration."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from mconet.core.domain.authorization import Authorization
from mconet.core.domain.extensions import Extensions
from mconet.core.domain.headers import Headers
from mconet.core.domain.query_parameters import QueryParameters
from mconet.core.domain.uri import UriValue


@runtime_checkable
class ServiceAccess(Protocol):
    """Keep endpoint, authorization, and request context independent.

    Implementations expose unresolved access input without inheriting an SDK
    base class. Field merging, URI validation, authorization resolution, and
    transport mapping are deliberately owned by later runtime components.
    """

    @property
    def endpoint(self) -> UriValue | None:
        """Return an optional service endpoint URI value."""
        # Preserve the producer's absolute/relative declaration; this protocol
        # does not validate schemes or resolve a missing endpoint.
        ...

    @property
    def authorization(self) -> Authorization | None:
        """Return optional unresolved authorization input."""
        # None means authorization is not configured at this input layer. A
        # resolver later produces an explicit authorization implementation.
        ...

    @property
    def headers(self) -> Headers:
        """Return ordered non-sensitive custom header values."""
        # Headers remain separate from authorization so ordinary access context
        # cannot become an alternate container for credentials.
        ...

    @property
    def query(self) -> QueryParameters:
        """Return ordered non-sensitive custom query parameters."""
        # Query values are passed through without URL encoding or authorization
        # interpretation; the selected transport owns final serialization.
        ...

    @property
    def api_version(self) -> str | None:
        """Return an optional service API version context value."""
        # The value remains provider-owned text and is not inferred from the
        # endpoint, model, or interaction protocol.
        ...

    @property
    def project_id(self) -> str | None:
        """Return an optional provider project identifier."""
        # Keep project selection independent from credentials and tenant scope
        # so later merge rules can replace each field explicitly.
        ...

    @property
    def tenant_id(self) -> str | None:
        """Return an optional provider tenant identifier."""
        # Tenant context is opaque provider data at this boundary; no naming or
        # hierarchy rules are imposed by the structural contract.
        ...

    @property
    def extensions(self) -> Extensions:
        """Return unknown versioned access fields for forward compatibility."""
        # Unknown non-sensitive values remain observable without adding fixed
        # fields to the core contract for every provider-specific capability.
        ...
