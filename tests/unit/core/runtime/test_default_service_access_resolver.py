"""Field-precedence tests for the default service access resolver."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import cast

from mconet.core.domain import (
    Authorization,
    Extensions,
    HeaderField,
    Headers,
    ModelInteractionError,
    OpenIdentifier,
    QueryParameter,
    QueryParameters,
    ResolvedServiceAccess,
    ServiceAccess,
    UriValue,
)
from mconet.core.runtime.default_service_access_resolver import (
    DefaultServiceAccessResolver,
)
from mconet.core.spi import ServiceAccessResolver
from mconet.testing import ServiceAccessResolverContractSuite


def _empty_extensions() -> Extensions:
    """Create independent extension storage for one access fixture."""
    # A fresh mapping keeps fixture layers from sharing membership before the
    # resolver observes their original values.
    return {}


@dataclass(frozen=True, slots=True)
class _Authorization:
    """Opaque authorization retained as one atomic access field."""

    kind: OpenIdentifier
    """Non-sensitive handler-selection discriminator."""

    label: str
    """Test-only marker proving the selected object is not rebuilt."""


@dataclass(slots=True)
class _Access:
    """Mutable structural access layer used to observe resolver side effects."""

    endpoint: UriValue | None
    """Optional endpoint supplied by this configuration layer."""

    authorization: Authorization | None
    """Optional opaque authorization supplied as one atomic value."""

    headers: Headers
    """Ordered non-sensitive headers supplied by this layer."""

    query: QueryParameters
    """Ordered non-sensitive query parameters supplied by this layer."""

    api_version: str | None = None
    """Optional API version supplied by this layer."""

    project_id: str | None = None
    """Optional project identifier supplied by this layer."""

    tenant_id: str | None = None
    """Optional tenant identifier supplied by this layer."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Portable provider-specific access facts."""


def _authorization(label: str) -> _Authorization:
    """Build one opaque authorization distinguished by an exact object."""
    return _Authorization(OpenIdentifier(f"authorization.{label}"), label)


def _endpoint(label: str) -> UriValue:
    """Build one absolute endpoint whose host identifies its source layer."""
    return UriValue(f"https://{label}.models.example.test/v1", True)


def _headers(*pairs: tuple[str, str]) -> Headers:
    """Build ordered headers without folding names or merging duplicates."""
    return Headers(tuple(HeaderField(name, value) for name, value in pairs))


def _query(*pairs: tuple[str, str]) -> QueryParameters:
    """Build ordered query parameters without encoding or deduplication."""
    return QueryParameters(tuple(QueryParameter(name, value) for name, value in pairs))


class _Unset:
    """Mark a test argument that should receive the layer label's own value."""


_UNSET = _Unset()


def _access(
    label: str,
    *,
    endpoint: UriValue | _Unset | None = _UNSET,
    authorization: Authorization | _Unset | None = _UNSET,
    headers: Headers | None = None,
    query: QueryParameters | None = None,
    api_version: str | _Unset | None = _UNSET,
    project_id: str | _Unset | None = _UNSET,
    tenant_id: str | _Unset | None = _UNSET,
    extensions: Extensions | None = None,
) -> _Access:
    """Build one labeled layer, using the unset marker for label-owned values."""
    # The marker distinguishes an omitted argument from an explicit None, so a
    # case can leave a field absent without losing the layer's other facts.
    return _Access(
        endpoint=_endpoint(label) if isinstance(endpoint, _Unset) else endpoint,
        authorization=(
            _authorization(label)
            if isinstance(authorization, _Unset)
            else authorization
        ),
        headers=_headers(("X-Layer", label)) if headers is None else headers,
        query=_query(("layer", label)) if query is None else query,
        api_version=label if isinstance(api_version, _Unset) else api_version,
        project_id=(
            f"project-{label}" if isinstance(project_id, _Unset) else project_id
        ),
        tenant_id=(f"tenant-{label}" if isinstance(tenant_id, _Unset) else tenant_id),
        extensions={"source": label} if extensions is None else extensions,
    )


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> BaseException:
    """Require an action to raise the expected exception and message fragment."""
    try:
        action()
    except exception_type as error:
        # The fragment distinguishes a precedence failure from a type error.
        assert message in str(error)
        return error
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_default_resolver_selects_each_field_from_its_highest_layer() -> None:
    """Verify one explicit field does not promote sibling fields from its layer."""
    interaction = _access(
        "interaction",
        authorization=None,
        headers=Headers(),
        query=QueryParameters(),
        api_version=None,
        project_id=None,
        tenant_id=None,
        extensions={},
    )
    request = _access(
        "request",
        endpoint=None,
        headers=Headers(),
        query=QueryParameters(),
        project_id=None,
        tenant_id=None,
        extensions={},
    )
    client = _access(
        "client",
        endpoint=None,
        authorization=None,
        query=QueryParameters(),
        api_version=None,
        tenant_id=None,
        extensions={},
    )
    protocol = _access(
        "protocol",
        endpoint=None,
        authorization=None,
        api_version=None,
        project_id=None,
    )
    request_authorization = request.authorization

    resolved = DefaultServiceAccessResolver().resolve(
        interaction,
        request,
        client,
        protocol,
    )

    # Interaction supplies only the endpoint. Request, client, and protocol
    # defaults each contribute a different remaining field.
    assert resolved.endpoint is interaction.endpoint
    assert resolved.authorization is request_authorization
    assert resolved.headers is client.headers
    assert resolved.query is protocol.query
    assert resolved.api_version == "request"
    assert resolved.project_id == "project-client"
    assert resolved.tenant_id == "tenant-protocol"
    assert resolved.extensions["source"] == "protocol"
    assert interaction.endpoint is not None
    assert resolved.endpoint == interaction.endpoint


def test_default_resolver_lets_higher_fields_replace_lower_fields() -> None:
    """Verify request, client, and protocol values lose to a higher explicit field."""
    interaction = _access("interaction")
    request = _access("request")
    client = _access("client")
    protocol = _access("protocol")

    resolved = DefaultServiceAccessResolver().resolve(
        interaction,
        request,
        client,
        protocol,
    )

    # The highest layer replaces each whole field. Header and query members from
    # lower layers are not appended, and authorization is not reconstructed.
    assert resolved.endpoint is interaction.endpoint
    assert resolved.authorization is interaction.authorization
    assert resolved.headers is interaction.headers
    assert resolved.query is interaction.query
    assert resolved.api_version == "interaction"
    assert resolved.project_id == "project-interaction"
    assert resolved.tenant_id == "tenant-interaction"
    assert dict(resolved.extensions) == {"source": "interaction"}
    assert resolved.headers.get_all("X-Layer") == ("interaction",)
    assert resolved.query.values == (QueryParameter("layer", "interaction"),)


def test_default_resolver_preserves_repeated_header_and_query_order() -> None:
    """Verify the winning collections keep duplicate names and original order."""
    headers = _headers(("X-Trace", "one"), ("X-Trace", "two"))
    query = _query(("region", "east"), ("region", "west"))
    interaction = _access(
        "interaction",
        headers=headers,
        query=query,
        extensions={"priority": 1, "region": "east"},
    )

    resolved = DefaultServiceAccessResolver().resolve(interaction, None, None, None)

    # Identity preserves order and repetition without a memberwise merge that
    # could sort names or collapse duplicates.
    assert resolved.headers is headers
    assert resolved.query is query
    assert resolved.headers.values == headers.values
    assert list(resolved.extensions) == ["priority", "region"]


def test_default_resolver_treats_empty_collections_as_absent() -> None:
    """Verify an empty collection falls through to the next configured layer."""
    interaction = _access(
        "interaction",
        headers=Headers(),
        query=QueryParameters(),
        extensions={},
    )
    request = _access("request", headers=Headers(), query=QueryParameters())
    client = _access("client")

    resolved = DefaultServiceAccessResolver().resolve(
        interaction,
        request,
        client,
        None,
    )

    # Emptiness is the absence signal for collections that cannot be None.
    # Request extensions therefore win only because the interaction map is empty.
    assert resolved.headers is client.headers
    assert resolved.query is client.query
    assert resolved.extensions["source"] == "request"


def test_default_resolver_keeps_explicit_empty_context_text() -> None:
    """Verify an empty string overrides a lower non-empty context value."""
    interaction = _access(
        "interaction",
        api_version="",
        project_id="",
        tenant_id="",
    )
    protocol = _access("protocol")

    resolved = DefaultServiceAccessResolver().resolve(interaction, None, None, protocol)

    # Empty text is present provider context. Truthiness must not discard it in
    # favor of the protocol default.
    assert resolved.api_version == ""
    assert resolved.project_id == ""
    assert resolved.tenant_id == ""


def test_default_resolver_skips_absent_layers_without_shifting_fields() -> None:
    """Verify a missing layer does not let the next layer change field priority."""
    client = _access("client", authorization=None, endpoint=None)
    protocol = _access("protocol")

    resolved = DefaultServiceAccessResolver().resolve(None, None, client, protocol)

    # Client still outranks the protocol default for the fields it sets, while
    # absent interaction and request layers do not become empty access objects.
    assert resolved.endpoint is protocol.endpoint
    assert resolved.authorization is protocol.authorization
    assert resolved.api_version == "client"
    assert resolved.project_id == "project-client"


def test_default_resolver_rejects_missing_authorization_without_source_text() -> None:
    """Verify omitted authorization is distinct from an explicit decision."""
    endpoint = UriValue("https://secret-host.example.test/v1", True)
    interaction = _access(
        "interaction",
        endpoint=endpoint,
        authorization=None,
        headers=_headers(
            ("X-Trace", "trace-value"),
        ),
    )

    error = _assert_raises(
        ModelInteractionError,
        lambda: DefaultServiceAccessResolver().resolve(interaction, None, None, None),
        "authorization is not configured",
    )

    # The failure is a configuration omission. It is not an authentication
    # attempt, and it must not echo endpoint or header text.
    assert isinstance(error, ModelInteractionError)
    assert str(error.category.id) == "invalid_request"
    assert str(error.phase.id) == "service_access_resolution"
    assert error.code == "missing_authorization"
    assert error.status_code is None
    assert error.cause is None
    rendered = f"{error} {error.message}"
    assert "secret-host.example.test" not in rendered
    assert "trace-value" not in rendered


def test_default_resolver_rejects_all_absent_layers() -> None:
    """Verify four absent layers cannot produce a partial access snapshot."""
    error = _assert_raises(
        ModelInteractionError,
        lambda: DefaultServiceAccessResolver().resolve(None, None, None, None),
        "authorization is not configured",
    )

    assert isinstance(error, ModelInteractionError)
    assert error.code == "missing_authorization"


def test_default_resolver_rejects_invalid_lower_layers() -> None:
    """Verify precedence cannot hide an invalid client or protocol value."""
    interaction = _access("interaction")
    client = _access(
        "client",
        headers=_headers(("Bad Name", "value")),
    )

    # The client header is illegal even though the interaction header replaces
    # it. Validation belongs to every supplied layer before selection.
    _assert_raises(
        ValueError,
        lambda: DefaultServiceAccessResolver().resolve(
            interaction,
            None,
            client,
            None,
        ),
        "header name must be an HTTP token",
    )


def test_default_resolver_names_a_layer_with_the_wrong_type() -> None:
    """Verify a non-access object fails as that argument, not as a merge."""
    error = _assert_raises(
        TypeError,
        lambda: DefaultServiceAccessResolver().resolve(
            None,
            cast_access(object()),
            None,
            None,
        ),
        "request_service_access must implement ServiceAccess",
    )

    assert isinstance(error, TypeError)


def cast_access(value: object) -> ServiceAccess:
    """Pass one dynamically typed object through the resolver boundary."""
    # The cast is the boundary under test. The resolver must reject the value
    # before reading any access field from it.
    return cast(ServiceAccess, value)


def test_default_resolver_does_not_read_authorization_material() -> None:
    """Verify selection keeps the authorization object opaque."""

    class _GuardedAuthorization:
        """Authorization whose non-kind attribute fails if resolution reads it."""

        def __init__(self) -> None:
            self.kind = OpenIdentifier("authorization.guarded")

        def read_protected_material(self) -> str:
            """Fail if resolution inspects anything beyond the open kind."""
            raise AssertionError("resolver read authorization material")

    authorization = _GuardedAuthorization()
    interaction = _access("interaction", authorization=authorization)

    resolved = DefaultServiceAccessResolver().resolve(interaction, None, None, None)

    # The same object is selected. Calling the guard here proves it would have
    # failed inside resolve if the resolver had read past the open kind.
    assert resolved.authorization is authorization
    read_material = authorization.read_protected_material
    try:
        read_material()
    except AssertionError as error:
        assert "authorization material" in str(error)
    else:
        raise AssertionError("Expected guarded authorization material to fail.")


def test_default_resolver_detaches_extension_membership() -> None:
    """Verify later source-map edits do not change the resolved snapshot."""
    extensions: dict[str, str] = {"source": "interaction"}
    interaction = _access("interaction", extensions=extensions)

    resolved = DefaultServiceAccessResolver().resolve(interaction, None, None, None)
    extensions["source"] = "changed"
    extensions["added"] = "later"

    # Top-level membership is copied at resolution. Nested JSON identity is the
    # resolved snapshot's own contract and is not reimplemented here.
    assert dict(resolved.extensions) == {"source": "interaction"}
    assert "added" not in resolved.extensions


def test_default_resolver_satisfies_the_access_contract_suite() -> None:
    """Verify a split-field success leaves every source layer unchanged."""
    interaction = _access(
        "interaction",
        authorization=None,
        headers=Headers(),
        query=QueryParameters(),
        api_version=None,
        project_id=None,
        tenant_id=None,
        extensions={},
    )
    request = _access(
        "request",
        endpoint=None,
        headers=Headers(),
        query=QueryParameters(),
        project_id=None,
        tenant_id=None,
        extensions={},
    )
    client = _access(
        "client",
        endpoint=None,
        authorization=None,
        query=QueryParameters(),
        api_version=None,
        tenant_id=None,
        extensions={},
    )
    protocol = _access(
        "protocol",
        headers=Headers(),
        api_version=None,
        project_id=None,
    )
    interaction_extensions = dict(interaction.extensions)

    def assert_access(actual: ResolvedServiceAccess) -> None:
        """Require the field winners selected by the four source layers."""
        assert actual.endpoint is interaction.endpoint
        assert actual.authorization is request.authorization
        assert actual.headers is client.headers
        assert actual.query is protocol.query
        assert actual.api_version == "request"
        assert actual.project_id == "project-client"
        assert actual.tenant_id == "tenant-protocol"

    ServiceAccessResolverContractSuite(DefaultServiceAccessResolver()).assert_resolve(
        interaction,
        request,
        client,
        protocol,
        assertion=assert_access,
    )

    # The suite checks source safety. This repeats the mutable extension fact
    # that distinguishes a copied snapshot from a resolver writing the source.
    assert interaction.extensions == interaction_extensions


def test_default_resolver_reports_missing_authorization_through_the_suite() -> None:
    """Verify the contract suite observes the omission failure and intact sources."""
    interaction = _access("interaction", authorization=None)
    observed: list[BaseException] = []

    def assert_failure(actual: BaseException) -> None:
        """Require the stable omission code without a partial snapshot."""
        assert isinstance(actual, ModelInteractionError)
        assert actual.code == "missing_authorization"
        observed.append(actual)

    ServiceAccessResolverContractSuite(
        DefaultServiceAccessResolver()
    ).assert_resolve_failure(
        interaction,
        None,
        None,
        None,
        assertion=assert_failure,
    )

    assert len(observed) == 1
    assert interaction.headers.get_all("X-Layer") == ("interaction",)


def test_default_resolver_is_a_stateless_builtin_component() -> None:
    """Verify ordinary instances satisfy the resolver protocol."""
    first = DefaultServiceAccessResolver()
    second = DefaultServiceAccessResolver()

    # Structural conformance needs no base class. Shared metadata stays
    # diagnostic and declares neither a data port nor a capability.
    assert isinstance(first, ServiceAccessResolver)
    assert first.descriptor is second.descriptor
    assert first.descriptor.name == "default-service-access-resolver"
    assert first.descriptor.version == "1.0.0"
    assert first.descriptor.source == "builtin"
    assert first.descriptor.type_contract is None
    assert first.descriptor.capabilities == frozenset()
