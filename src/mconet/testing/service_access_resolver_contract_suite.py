"""Reusable resolution and source-safety assertions for access resolvers."""

from __future__ import annotations

from collections.abc import Callable
from inspect import iscoroutinefunction
from typing import TypeVar, cast

from mconet.core.domain import (
    Authorization,
    Headers,
    OpenIdentifier,
    QueryParameters,
    ResolvedServiceAccess,
    ServiceAccess,
    UriValue,
    validate_service_access,
)
from mconet.core.spi import ComponentDescriptor, ServiceAccessResolver
from mconet.testing._json_value_snapshot import (
    JsonValueSnapshot,
    snapshot_json_value,
)

_ValueT = TypeVar("_ValueT")
_SourceTuple = tuple[
    ServiceAccess | None,
    ServiceAccess | None,
    ServiceAccess | None,
    ServiceAccess | None,
]
_AccessSnapshot = tuple[
    UriValue | None,
    Authorization | None,
    OpenIdentifier | None,
    Headers,
    QueryParameters,
    str | None,
    str | None,
    str | None,
    JsonValueSnapshot,
]
_SOURCE_MUTATION_MESSAGE = "resolver must not mutate service access sources."


class ServiceAccessResolverContractSuite:
    """Apply successful, failing, and source-safety resolver contracts.

    The suite is independent of pytest, unittest, concrete authorization kinds,
    provider protocols, fixture formats, and field-merging implementations.
    Callers provide four access layers in their public priority order and inspect
    the exact resolved snapshot or exact failure through a synchronous callback.

    Runtime checks supplement static protocol conformance. A successful result
    must use the nominal immutable :class:`ResolvedServiceAccess` type. Before
    invoking ``resolve``, the suite validates and snapshots every present source;
    after completion or failure it requires all public access fields to remain
    unchanged. Authorization is treated atomically by identity and kind, without
    reading credentials or implementation-owned data.

    Each assertion invokes ``resolve`` exactly once. The suite performs no field
    merge, endpoint normalization, credential resolution, authorization, request
    mutation, registry lookup, transport, network I/O, fallback, retry, logging,
    or retention of access sources after the operation returns.
    """

    __slots__ = ("_resolver",)

    def __init__(self, resolver: ServiceAccessResolver) -> None:
        """Validate and retain one structurally conforming sync resolver.

        Args:
            resolver: Custom or SDK resolver subjected to reusable cases.

        Raises:
            TypeError: If the object, descriptor, or resolve operation violates
                the public resolver boundary.
        """
        resolver_value = cast(object, resolver)
        if not isinstance(resolver_value, ServiceAccessResolver):
            raise TypeError("resolver must implement ServiceAccessResolver.")
        descriptor_value = cast(object, resolver.descriptor)
        if not isinstance(descriptor_value, ComponentDescriptor):
            raise TypeError("resolver descriptor must be a ComponentDescriptor.")

        # Access resolution is a synchronous configuration step. Reject async
        # look-alikes before any source snapshot or resolver side effect occurs.
        resolve = resolver.resolve
        if iscoroutinefunction(resolve) or iscoroutinefunction(type(resolve).__call__):
            raise TypeError("resolver operation must be synchronous.")
        self._resolver = resolver

    def assert_resolve(
        self,
        interaction_override: ServiceAccess | None,
        request_service_access: ServiceAccess | None,
        client_default_service_access: ServiceAccess | None,
        protocol_default_service_access: ServiceAccess | None,
        *,
        assertion: Callable[[ResolvedServiceAccess], None],
    ) -> None:
        """Validate one successful immutable access resolution.

        Args:
            interaction_override: Highest-priority optional access source.
            request_service_access: Optional request-owned access source.
            client_default_service_access: Optional client default source.
            protocol_default_service_access: Lowest-priority protocol default.
            assertion: Synchronous callback asserting field-level merge facts.

        Raises:
            TypeError: If a source or ``assertion`` violates its public shape.
            AssertionError: If the result is invalid or any source is changed.
            BaseException: Any exact resolver or assertion callback failure.
        """
        # Complete callback and source validation before the only resolver call
        # so malformed case setup cannot be mistaken for resolver behavior.
        checked_assertion = _validate_assertion(assertion)
        sources = _sources(
            interaction_override,
            request_service_access,
            client_default_service_access,
            protocol_default_service_access,
        )
        snapshots = _validate_and_snapshot_sources(sources)

        actual = self._resolver.resolve(
            interaction_override,
            request_service_access,
            client_default_service_access,
            protocol_default_service_access,
        )
        # Source immutability is checked before result shape and callback logic,
        # making a resolver mutation the primary contract violation.
        _assert_sources_unchanged(sources, snapshots)
        actual_value = cast(object, actual)
        if not isinstance(actual_value, ResolvedServiceAccess):
            raise AssertionError("resolver must return a ResolvedServiceAccess.")
        checked_assertion(actual_value)

    def assert_resolve_failure(
        self,
        interaction_override: ServiceAccess | None,
        request_service_access: ServiceAccess | None,
        client_default_service_access: ServiceAccess | None,
        protocol_default_service_access: ServiceAccess | None,
        *,
        assertion: Callable[[BaseException], None],
    ) -> None:
        """Require access resolution to fail without changing any source.

        Args:
            interaction_override: Highest-priority optional access source.
            request_service_access: Optional request-owned access source.
            client_default_service_access: Optional client default source.
            protocol_default_service_access: Lowest-priority protocol default.
            assertion: Synchronous callback asserting exact failure facts.

        Raises:
            TypeError: If a source or ``assertion`` violates its public shape.
            AssertionError: If resolution succeeds or any source is changed.
            BaseException: Any exact assertion callback failure.
        """
        # Snapshot before resolution so failure paths receive the same source
        # immutability guarantee as successful field-level merge cases.
        checked_assertion = _validate_assertion(assertion)
        sources = _sources(
            interaction_override,
            request_service_access,
            client_default_service_access,
            protocol_default_service_access,
        )
        snapshots = _validate_and_snapshot_sources(sources)

        try:
            # Catch BaseException deliberately so custom fixture interruption or
            # cancellation remains exact at this synchronous contract boundary.
            self._resolver.resolve(
                interaction_override,
                request_service_access,
                client_default_service_access,
                protocol_default_service_access,
            )
        except BaseException as error:
            captured_error = error
        else:
            _assert_sources_unchanged(sources, snapshots)
            raise AssertionError("resolver was expected to fail access resolution.")

        # Check source safety before exposing the resolver error. The callback is
        # outside the catch block so its own failure cannot be misclassified.
        _assert_sources_unchanged(sources, snapshots)
        checked_assertion(captured_error)


def _sources(
    interaction_override: ServiceAccess | None,
    request_service_access: ServiceAccess | None,
    client_default_service_access: ServiceAccess | None,
    protocol_default_service_access: ServiceAccess | None,
) -> _SourceTuple:
    """Return all source references in the resolver's public priority order."""
    # One immutable tuple gives validation and post-call comparison the exact
    # same source positions without merging or replacing absent layers.
    return (
        interaction_override,
        request_service_access,
        client_default_service_access,
        protocol_default_service_access,
    )


def _validate_and_snapshot_sources(
    sources: _SourceTuple,
) -> tuple[_AccessSnapshot | None, ...]:
    """Validate present layers and copy their observable non-secret state."""
    snapshots: list[_AccessSnapshot | None] = []
    for source in sources:
        if source is None:
            # Preserve absence as its own priority-layer fact instead of creating
            # an empty ServiceAccess value with different inheritance semantics.
            snapshots.append(None)
            continue
        validate_service_access(source)
        snapshots.append(_snapshot_access(source))
    return tuple(snapshots)


def _snapshot_access(access: ServiceAccess) -> _AccessSnapshot:
    """Capture one validated source without inspecting authorization secrets."""
    authorization = access.authorization
    authorization_kind = authorization.kind if authorization is not None else None
    extensions = snapshot_json_value(dict(access.extensions))

    # Nominal endpoint, header, and query values are immutable. Authorization is
    # retained only as an opaque reference plus its non-sensitive selection kind;
    # portable extensions use an iterative snapshot to expose nested mutation.
    return (
        access.endpoint,
        authorization,
        authorization_kind,
        access.headers,
        access.query,
        access.api_version,
        access.project_id,
        access.tenant_id,
        extensions,
    )


def _assert_sources_unchanged(
    sources: _SourceTuple,
    snapshots: tuple[_AccessSnapshot | None, ...],
) -> None:
    """Require every source to preserve its complete public observable state."""
    for source, snapshot in zip(sources, snapshots, strict=True):
        if source is None or snapshot is None:
            # Both tuples originate from the same positions. A mixed state would
            # indicate an internal suite invariant failure and is rejected below.
            if source is not None or snapshot is not None:
                raise AssertionError(_SOURCE_MUTATION_MESSAGE)
            continue
        if not _source_matches_snapshot(source, snapshot):
            raise AssertionError(_SOURCE_MUTATION_MESSAGE)


def _source_matches_snapshot(
    access: ServiceAccess,
    snapshot: _AccessSnapshot,
) -> bool:
    """Return whether one source still exposes its exact pre-call state."""
    try:
        # Revalidation detects a resolver replacing a field with an invalid or
        # cyclic value before the iterative snapshot assumes valid JSON shape.
        validate_service_access(access)
        authorization = access.authorization
        authorization_kind = authorization.kind if authorization is not None else None
        current_extensions = snapshot_json_value(dict(access.extensions))

        # Authorization identity prevents replacement of the atomic policy value;
        # kind equality also detects mutation visible to later handler selection.
        scalar_and_value_fields_match = (
            access.endpoint == snapshot[0]
            and authorization is snapshot[1]
            and authorization_kind == snapshot[2]
            and access.headers == snapshot[3]
            and access.query == snapshot[4]
            and access.api_version == snapshot[5]
            and access.project_id == snapshot[6]
            and access.tenant_id == snapshot[7]
        )
        return scalar_and_value_fields_match and current_extensions == snapshot[8]
    except BaseException:
        # A resolver may have replaced a field with unreadable or malformed data.
        # Fail closed using implementation-owned text and no source representation.
        return False


def _validate_assertion(
    assertion: Callable[[_ValueT], None],
) -> Callable[[_ValueT], None]:
    """Require one synchronous assertion before invoking the resolver."""
    assertion_value = cast(object, assertion)
    if not callable(assertion_value):
        raise TypeError("assertion must be callable.")
    if iscoroutinefunction(assertion) or iscoroutinefunction(type(assertion).__call__):
        # Async callbacks would leave their body unexecuted and create an
        # unawaited coroutine in this deliberately synchronous suite.
        raise TypeError("assertion must be synchronous.")
    return assertion
