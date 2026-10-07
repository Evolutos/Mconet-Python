"""Resolution, precedence, and source-safety tests for the access suite."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import cast, get_type_hints

from mconet.core.domain import (
    Authorization,
    Extensions,
    HeaderField,
    Headers,
    JsonValue,
    OpenIdentifier,
    QueryParameter,
    QueryParameters,
    ResolvedServiceAccess,
    ServiceAccess,
    UriValue,
)
from mconet.core.spi import ComponentDescriptor, ServiceAccessResolver
from mconet.testing import (
    ComponentCallRecorder,
    ServiceAccessResolverContractSuite,
    StubServiceAccessResolver,
)


def _empty_extensions() -> Extensions:
    """Create independent portable storage for access fixtures."""
    # Fresh mappings prevent separate priority layers from sharing mutation
    # before or during one resolver contract case.
    return {}


@dataclass(frozen=True, slots=True)
class _Authorization:
    """Opaque authorization fixture kept atomic during access resolution."""

    kind: OpenIdentifier
    """Non-sensitive handler-selection discriminator."""


@dataclass(slots=True)
class _Access:
    """Mutable structural access fixture used to detect resolver side effects."""

    endpoint: UriValue | None
    """Optional service endpoint supplied by this layer."""

    authorization: Authorization | None
    """Optional opaque authorization supplied by this layer."""

    headers: Headers
    """Ordered non-sensitive headers supplied by this layer."""

    query: QueryParameters
    """Ordered non-sensitive query values supplied by this layer."""

    api_version: str | None = None
    """Optional provider API version context."""

    project_id: str | None = None
    """Optional provider project context."""

    tenant_id: str | None = None
    """Optional provider tenant context."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Portable provider-specific non-sensitive facts."""


class _RecordingResolver:
    """Structural resolver recording the ordered sources and one outcome."""

    __slots__ = ("_calls", "_descriptor", "_error", "_recorder", "_result")

    def __init__(
        self,
        result: ResolvedServiceAccess,
        recorder: ComponentCallRecorder,
        *,
        error: BaseException | None = None,
    ) -> None:
        """Retain one outcome and initialize exact call evidence."""
        self._descriptor = ComponentDescriptor(
            "Recording access resolver", "1", "application"
        )
        self._result = result
        self._error = error
        self._recorder = recorder
        self._calls: list[
            tuple[
                ServiceAccess | None,
                ServiceAccess | None,
                ServiceAccess | None,
                ServiceAccess | None,
            ]
        ] = []

    @property
    def descriptor(self) -> ComponentDescriptor:
        """Return valid immutable resolver metadata."""
        # Return the exact retained descriptor so suite construction cannot
        # observe dynamically replaced component metadata.
        return self._descriptor

    @property
    def calls(
        self,
    ) -> tuple[
        tuple[
            ServiceAccess | None,
            ServiceAccess | None,
            ServiceAccess | None,
            ServiceAccess | None,
        ],
        ...,
    ]:
        """Return an immutable snapshot of ordered resolver calls."""
        # Tuple conversion protects evidence membership while preserving source
        # references and their priority positions by identity.
        return tuple(self._calls)

    def resolve(
        self,
        interaction_override: ServiceAccess | None,
        request_service_access: ServiceAccess | None,
        client_default_service_access: ServiceAccess | None,
        protocol_default_service_access: ServiceAccess | None,
    ) -> ResolvedServiceAccess:
        """Record all sources once, then return or raise the configured outcome."""
        # Recording before outcome delivery proves both success and failure use
        # one complete call without hidden fallback resolution.
        self._recorder.record("resolve_service_access")
        self._calls.append(
            (
                interaction_override,
                request_service_access,
                client_default_service_access,
                protocol_default_service_access,
            )
        )
        if self._error is not None:
            raise self._error
        return self._result


class _MutatingResolver:
    """Resolver intentionally changing one source before its configured outcome."""

    __slots__ = ("_error", "_result")

    descriptor = ComponentDescriptor("Mutating resolver", "1", "application")
    """Valid metadata isolates source-safety enforcement."""

    def __init__(
        self,
        result: ResolvedServiceAccess,
        *,
        error: BaseException | None = None,
    ) -> None:
        """Retain one result and optional failure used after mutation."""
        self._result = result
        self._error = error

    def resolve(
        self,
        interaction_override: ServiceAccess | None,
        request_service_access: ServiceAccess | None,
        client_default_service_access: ServiceAccess | None,
        protocol_default_service_access: ServiceAccess | None,
    ) -> ResolvedServiceAccess:
        """Mutate nested extension data, then return or raise."""
        # The fixture uses the known mutable access implementation only to prove
        # the suite compares nested public state after every resolver outcome.
        del (
            request_service_access,
            client_default_service_access,
            protocol_default_service_access,
        )
        if not isinstance(interaction_override, _Access):
            raise AssertionError("Mutation fixture requires an _Access override.")
        mutable_extensions = cast(dict[str, object], interaction_override.extensions)
        nested = cast(dict[str, object], mutable_extensions["nested"])
        nested["value"] = "changed"
        if self._error is not None:
            raise self._error
        return self._result


class _MalformedResultResolver:
    """Claim the resolver signature while returning an invalid result."""

    descriptor = ComponentDescriptor("Malformed resolver", "1", "application")
    """Valid metadata keeps result validation isolated."""

    def resolve(
        self,
        interaction_override: ServiceAccess | None,
        request_service_access: ServiceAccess | None,
        client_default_service_access: ServiceAccess | None,
        protocol_default_service_access: ServiceAccess | None,
    ) -> ResolvedServiceAccess:
        """Discard valid sources and return a dynamically malformed value."""
        # Dynamic casting crosses static checking so the Suite's nominal result
        # guard is the only intended failure in this case.
        del (
            interaction_override,
            request_service_access,
            client_default_service_access,
            protocol_default_service_access,
        )
        return cast(ResolvedServiceAccess, object())


class _IncompleteResolver:
    """Component-shaped object intentionally missing resolve behavior."""

    descriptor = ComponentDescriptor("Incomplete resolver", "1", "application")
    """Valid metadata isolates structural protocol rejection."""


class _InvalidDescriptorResolver:
    """Complete resolver behavior paired with invalid component metadata."""

    descriptor = cast(ComponentDescriptor, object())
    """Malformed metadata used only for constructor validation."""

    def resolve(
        self,
        interaction_override: ServiceAccess | None,
        request_service_access: ServiceAccess | None,
        client_default_service_access: ServiceAccess | None,
        protocol_default_service_access: ServiceAccess | None,
    ) -> ResolvedServiceAccess:
        """Discard sources and return a valid snapshot if called unexpectedly."""
        # Constructor validation must reject metadata before this behavior runs,
        # so a valid result keeps the malformed field unambiguous.
        del (
            interaction_override,
            request_service_access,
            client_default_service_access,
            protocol_default_service_access,
        )
        return _resolved_access()


class _AsyncResolver:
    """Expose an invalid asynchronous access resolution operation."""

    descriptor = ComponentDescriptor("Async resolver", "1", "application")
    """Valid metadata isolates synchronous-boundary rejection."""

    async def resolve(
        self,
        interaction_override: ServiceAccess | None,
        request_service_access: ServiceAccess | None,
        client_default_service_access: ServiceAccess | None,
        protocol_default_service_access: ServiceAccess | None,
    ) -> ResolvedServiceAccess:
        """Return a valid snapshot asynchronously if called unexpectedly."""
        # The Suite must reject the coroutine function without invoking it and
        # therefore without creating an unawaited coroutine object.
        del (
            interaction_override,
            request_service_access,
            client_default_service_access,
            protocol_default_service_access,
        )
        return _resolved_access()


def _source(label: str) -> _Access:
    """Build one complete valid access layer with distinguishable safe fields."""
    # Every source uses non-sensitive values so priority and mutation assertions
    # never place credential plaintext in ordinary headers or extensions.
    return _Access(
        endpoint=UriValue(f"https://{label}.models.example.test", True),
        authorization=_Authorization(OpenIdentifier(f"authorization.{label}")),
        headers=Headers((HeaderField("X-Source", label),)),
        query=QueryParameters((QueryParameter("source", label),)),
        api_version=f"version-{label}",
        project_id=f"project-{label}",
        tenant_id=f"tenant-{label}",
        extensions={"source": label, "nested": {"value": label}},
    )


def _resolved_access() -> ResolvedServiceAccess:
    """Build one complete immutable resolved access snapshot."""
    # Explicit fields prove the successful Suite path cannot accept unresolved
    # inheritance or a missing authorization decision.
    return ResolvedServiceAccess(
        endpoint=UriValue("https://resolved.models.example.test", True),
        authorization=_Authorization(OpenIdentifier("authorization.resolved")),
        headers=Headers((HeaderField("X-Source", "resolved"),)),
        query=QueryParameters((QueryParameter("source", "resolved"),)),
        api_version="version-resolved",
        project_id="project-resolved",
        tenant_id="tenant-resolved",
        extensions={"source": "resolved"},
    )


def _priority_result(
    interaction: _Access,
    request: _Access,
    client: _Access,
    protocol: _Access,
) -> ResolvedServiceAccess:
    """Build a result selecting distinguishable fields from ordered sources."""
    # The prebuilt result models field-level override evidence without embedding
    # a production merge algorithm in the test-kit contract implementation.
    if request.authorization is None:
        raise AssertionError("Priority fixture requires request authorization.")
    return ResolvedServiceAccess(
        endpoint=interaction.endpoint,
        authorization=request.authorization,
        headers=interaction.headers,
        query=request.query,
        api_version=request.api_version,
        project_id=client.project_id,
        tenant_id=protocol.tenant_id,
        extensions={"source": "priority-result"},
    )


def _sources() -> tuple[_Access, _Access, _Access, _Access]:
    """Build all four independent source layers in public priority order."""
    # Fresh objects make identity forwarding and source-state comparisons
    # independent for every test case.
    return (
        _source("interaction"),
        _source("request"),
        _source("client"),
        _source("protocol"),
    )


def _assert_nothing(value: object) -> None:
    """Accept a callback value when the test targets another boundary."""
    # Explicit disposal keeps the callable synchronous and documents that its
    # observed value must not affect the tested branch.
    del value


def _assert_type_error(action: Callable[[], object], message: str) -> None:
    """Require construction to fail with one exact type diagnostic."""
    try:
        action()
    except TypeError as error:
        assert str(error) == message
        return
    raise AssertionError("Expected contract setup to reject an invalid type.")


def _construct_incomplete_suite() -> object:
    """Attempt construction with a resolver missing required behavior."""
    # The cast intentionally crosses static checking so runtime protocol
    # conformance must reject the incomplete object.
    return ServiceAccessResolverContractSuite(
        cast(ServiceAccessResolver, _IncompleteResolver())
    )


def _construct_invalid_descriptor_suite() -> object:
    """Attempt construction with malformed component metadata."""
    # Complete resolve behavior isolates nominal descriptor validation.
    return ServiceAccessResolverContractSuite(_InvalidDescriptorResolver())


def _construct_async_suite() -> object:
    """Attempt construction with asynchronous resolution behavior."""
    # Runtime structural recognition accepts the method shape, while Suite
    # construction must additionally enforce synchronous completion.
    return ServiceAccessResolverContractSuite(
        cast(ServiceAccessResolver, _AsyncResolver())
    )


def test_suite_validates_field_override_result_and_exact_source_order() -> None:
    """Expose merged fields while preserving all four source identities."""
    interaction, request, client, protocol = _sources()
    expected = _priority_result(interaction, request, client, protocol)
    recorder = ComponentCallRecorder()
    resolver = _RecordingResolver(expected, recorder)

    def assert_access(actual: ResolvedServiceAccess) -> None:
        """Require exact result and each configured priority-selection fact."""
        assert actual is expected
        assert actual.endpoint is interaction.endpoint
        assert actual.authorization is request.authorization
        assert actual.headers is interaction.headers
        assert actual.query is request.query
        assert actual.api_version == request.api_version
        assert actual.project_id == client.project_id
        assert actual.tenant_id == protocol.tenant_id

    ServiceAccessResolverContractSuite(resolver).assert_resolve(
        interaction,
        request,
        client,
        protocol,
        assertion=assert_access,
    )

    assert recorder.calls == ("resolve_service_access",)
    assert resolver.calls == ((interaction, request, client, protocol),)
    assert resolver.calls[0][0] is interaction
    assert resolver.calls[0][1] is request
    assert resolver.calls[0][2] is client
    assert resolver.calls[0][3] is protocol


def test_suite_accepts_absent_layers_with_existing_stub() -> None:
    """Preserve None source layers and expose the exact configured snapshot."""
    expected = _resolved_access()
    resolver = StubServiceAccessResolver(
        ComponentDescriptor("Stub resolver", "1", "application"),
        expected,
    )
    observed: list[ResolvedServiceAccess] = []

    def assert_access(actual: ResolvedServiceAccess) -> None:
        """Require exact configured result from all absent sources."""
        assert actual is expected
        assert actual.authorization is expected.authorization
        observed.append(actual)

    ServiceAccessResolverContractSuite(resolver).assert_resolve(
        None,
        None,
        None,
        None,
        assertion=assert_access,
    )

    assert observed == [expected]


def test_suite_validates_exact_failure_without_partial_result() -> None:
    """Expose one resolver failure unchanged and keep every source intact."""
    sources = _sources()
    failure = ValueError("service access is incomplete")
    resolver = StubServiceAccessResolver(
        ComponentDescriptor("Stub resolver", "1", "application"),
        _resolved_access(),
        error=failure,
    )
    observed: list[BaseException] = []

    def assert_failure(actual: BaseException) -> None:
        """Require exact failure identity without fallback access."""
        assert actual is failure
        observed.append(actual)

    ServiceAccessResolverContractSuite(resolver).assert_resolve_failure(
        *sources,
        assertion=assert_failure,
    )

    assert observed == [failure]
    assert sources[0].api_version == "version-interaction"
    assert sources[0].extensions["nested"] == {"value": "interaction"}


def test_suite_rejects_nested_source_mutation_on_success_and_failure() -> None:
    """Detect nested extension changes before result or failure callbacks run."""
    success_sources = _sources()
    success_suite = ServiceAccessResolverContractSuite(
        _MutatingResolver(_resolved_access())
    )
    try:
        success_suite.assert_resolve(
            *success_sources,
            assertion=_assert_nothing,
        )
    except AssertionError as error:
        assert str(error) == "resolver must not mutate service access sources."
    else:
        raise AssertionError("Expected successful source mutation to fail.")

    failure_sources = _sources()
    resolver_failure = ValueError("resolution failed after mutation")
    callback_called = False

    def assert_failure(actual: BaseException) -> None:
        """Record an unexpected callback after source mutation."""
        nonlocal callback_called
        del actual
        callback_called = True

    failure_suite = ServiceAccessResolverContractSuite(
        _MutatingResolver(_resolved_access(), error=resolver_failure)
    )
    try:
        failure_suite.assert_resolve_failure(
            *failure_sources,
            assertion=assert_failure,
        )
    except AssertionError as error:
        assert str(error) == "resolver must not mutate service access sources."
        assert error is not resolver_failure
    else:
        raise AssertionError("Expected failing source mutation to fail closed.")

    assert not callback_called


def test_suite_snapshots_deep_extensions_without_python_recursion() -> None:
    """Keep valid source depth independent from recursive copying limits."""
    interaction = _source("interaction")
    deep_value: JsonValue = "leaf"
    for _ in range(2_000):
        # A separate list at every level creates a valid deeply nested JSON value
        # that recursive deepcopy or equality implementations cannot safely scan.
        deep_value = [deep_value]
    interaction.extensions = {"deep": deep_value}
    expected = _resolved_access()
    resolver = StubServiceAccessResolver(
        ComponentDescriptor("Stub resolver", "1", "application"),
        expected,
    )

    def assert_access(actual: ResolvedServiceAccess) -> None:
        """Require the exact configured result after deep source comparison."""
        assert actual is expected

    ServiceAccessResolverContractSuite(resolver).assert_resolve(
        interaction,
        None,
        None,
        None,
        assertion=assert_access,
    )

    assert interaction.extensions["deep"] is deep_value


def test_success_rejects_malformed_result_and_failure_rejects_success() -> None:
    """Require a nominal result and prevent fallback success in a failure case."""
    malformed_suite = ServiceAccessResolverContractSuite(_MalformedResultResolver())
    try:
        malformed_suite.assert_resolve(
            *_sources(),
            assertion=_assert_nothing,
        )
    except AssertionError as error:
        assert str(error) == "resolver must return a ResolvedServiceAccess."
    else:
        raise AssertionError("Expected a malformed resolved value to fail.")

    success_suite = ServiceAccessResolverContractSuite(
        StubServiceAccessResolver(
            ComponentDescriptor("Stub resolver", "1", "application"),
            _resolved_access(),
        )
    )
    try:
        success_suite.assert_resolve_failure(
            *_sources(),
            assertion=_assert_nothing,
        )
    except AssertionError as error:
        assert str(error) == "resolver was expected to fail access resolution."
    else:
        raise AssertionError("Expected failure-case success to be rejected.")


def test_suite_preserves_success_and_failure_callback_exceptions() -> None:
    """Propagate exact callback errors outside resolver control flow."""
    success_callback_error = RuntimeError("success assertion failed")
    resolution_failure = ValueError("resolution failed")
    failure_callback_error = RuntimeError("failure assertion failed")

    def fail_success_assertion(actual: ResolvedServiceAccess) -> None:
        """Raise one exact callback error after a valid success result."""
        del actual
        raise success_callback_error

    def fail_failure_assertion(actual: BaseException) -> None:
        """Confirm the resolver error, then raise one exact callback error."""
        assert actual is resolution_failure
        raise failure_callback_error

    success_suite = ServiceAccessResolverContractSuite(
        StubServiceAccessResolver(
            ComponentDescriptor("Success stub", "1", "application"),
            _resolved_access(),
        )
    )
    failure_suite = ServiceAccessResolverContractSuite(
        StubServiceAccessResolver(
            ComponentDescriptor("Failure stub", "1", "application"),
            _resolved_access(),
            error=resolution_failure,
        )
    )

    try:
        success_suite.assert_resolve(
            *_sources(),
            assertion=fail_success_assertion,
        )
    except RuntimeError as error:
        assert error is success_callback_error
    else:
        raise AssertionError("Expected the success assertion callback to fail.")

    try:
        failure_suite.assert_resolve_failure(
            *_sources(),
            assertion=fail_failure_assertion,
        )
    except RuntimeError as error:
        assert error is failure_callback_error
        assert error is not resolution_failure
    else:
        raise AssertionError("Expected the failure assertion callback to fail.")


def test_suite_rejects_invalid_resolver_shapes_at_construction() -> None:
    """Reject incomplete, malformed-metadata, and asynchronous resolvers."""
    _assert_type_error(
        _construct_incomplete_suite,
        "resolver must implement ServiceAccessResolver.",
    )
    _assert_type_error(
        _construct_invalid_descriptor_suite,
        "resolver descriptor must be a ComponentDescriptor.",
    )
    _assert_type_error(
        _construct_async_suite,
        "resolver operation must be synchronous.",
    )


def test_suite_validates_sources_and_callback_before_resolution() -> None:
    """Reject malformed case setup without invoking the resolver operation."""
    recorder = ComponentCallRecorder()
    resolver = _RecordingResolver(_resolved_access(), recorder)
    suite = ServiceAccessResolverContractSuite(resolver)

    try:
        suite.assert_resolve(
            cast(ServiceAccess, object()),
            None,
            None,
            None,
            assertion=_assert_nothing,
        )
    except TypeError as error:
        assert str(error) == "access must implement ServiceAccess."
    else:
        raise AssertionError("Expected invalid access to fail before resolution.")

    try:
        suite.assert_resolve(
            None,
            None,
            None,
            None,
            assertion=cast(Callable[[ResolvedServiceAccess], None], object()),
        )
    except TypeError as error:
        assert str(error) == "assertion must be callable."
    else:
        raise AssertionError("Expected a non-callable assertion to fail.")

    assert recorder.calls == ()
    assert resolver.calls == ()


def test_suite_rejects_async_assertion_before_resolution() -> None:
    """Prevent unawaited assertion callbacks from crossing the sync API."""
    recorder = ComponentCallRecorder()
    resolver = _RecordingResolver(_resolved_access(), recorder)

    async def assert_access(actual: ResolvedServiceAccess) -> None:
        """Represent one invalid asynchronous assertion callback."""
        # Discard the value because constructor validation must prevent this
        # coroutine function from ever being invoked.
        del actual

    try:
        ServiceAccessResolverContractSuite(resolver).assert_resolve(
            *_sources(),
            assertion=cast(
                Callable[[ResolvedServiceAccess], None],
                assert_access,
            ),
        )
    except TypeError as error:
        assert str(error) == "assertion must be synchronous."
    else:
        raise AssertionError("Expected an async assertion to be rejected.")

    assert recorder.calls == ()


def test_suite_exposes_exact_synchronous_resolution_surface() -> None:
    """Keep merging, credentials, authorization, and transport out of scope."""
    suite = ServiceAccessResolverContractSuite(
        StubServiceAccessResolver(
            ComponentDescriptor("Stub resolver", "1", "application"),
            _resolved_access(),
        )
    )
    expected_callback_types = {
        "assert_resolve": Callable[[ResolvedServiceAccess], None],
        "assert_resolve_failure": Callable[[BaseException], None],
    }

    for name, callback_type in expected_callback_types.items():
        # Both operations preserve the protocol's four priority positions and
        # differ only in the value delivered to the assertion callback.
        operation = getattr(ServiceAccessResolverContractSuite, name)
        signature = inspect.signature(operation)
        annotations = get_type_hints(operation)
        assert tuple(signature.parameters) == (
            "self",
            "interaction_override",
            "request_service_access",
            "client_default_service_access",
            "protocol_default_service_access",
            "assertion",
        )
        assert annotations == {
            "interaction_override": ServiceAccess | None,
            "request_service_access": ServiceAccess | None,
            "client_default_service_access": ServiceAccess | None,
            "protocol_default_service_access": ServiceAccess | None,
            "assertion": callback_type,
            "return": type(None),
        }
        assert not inspect.iscoroutinefunction(operation)

    for forbidden_member in (
        "merge",
        "read_credential",
        "resolve_credential",
        "authorize",
        "mutate_request",
        "send",
        "fetch",
        "register",
        "retry",
        "reset",
    ):
        assert not hasattr(suite, forbidden_member)
