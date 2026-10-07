"""Matching and request-boundary tests for AuthorizationHandlerContractSuite."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import cast, get_type_hints

from mconet.core.domain import (
    Authorization,
    Bytes,
    Extensions,
    HeaderField,
    Headers,
    MediaType,
    ModelDescriptor,
    ModelTarget,
    NamedModel,
    OpenIdentifier,
    QueryParameter,
    QueryParameters,
    Timestamp,
    UriValue,
)
from mconet.core.spi import (
    AuthorizationContext,
    AuthorizationHandler,
    BodySigningMode,
    BodySigningRequirement,
    ComponentDescriptor,
    MutableTransportRequest,
    TransportBody,
)
from mconet.testing import (
    AuthorizationHandlerContractSuite,
    ComponentCallRecorder,
    StubAuthorizationHandler,
)


def _empty_extensions() -> Extensions:
    """Create independent portable target extension storage."""
    return {}


@dataclass(frozen=True, slots=True)
class _Authorization:
    """Opaque authorization fixture containing no credential material."""

    kind: OpenIdentifier
    """Non-sensitive mechanism identifier used for handler matching."""


@dataclass(frozen=True, slots=True)
class _Target:
    """Complete structural model target for authorization context."""

    service_id: OpenIdentifier
    protocol_id: OpenIdentifier
    model: ModelDescriptor
    deployment_id: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


def _authorization() -> _Authorization:
    """Build one opaque authorization value with a valid kind."""
    return _Authorization(OpenIdentifier("authorization.fixture"))


def _context(mode: BodySigningMode = "none") -> AuthorizationContext:
    """Build complete immutable non-sensitive authorization facts."""
    target = _Target(
        OpenIdentifier("service.example"),
        OpenIdentifier("protocol.example"),
        NamedModel("model-example"),
    )
    return AuthorizationContext(
        interaction_id="interaction-1",
        target=cast(ModelTarget, target),
        endpoint=UriValue("https://models.example.test/v1", True),
        transport_kind=OpenIdentifier("http"),
        timestamp=Timestamp(1_800_000_000, 123_456_789),
        body_signing_mode=mode,
    )


def _request() -> MutableTransportRequest:
    """Build one encoded request with an open authorization window."""
    return MutableTransportRequest(
        method="POST",
        url=UriValue("https://models.example.test/v1/run", True),
        headers=Headers((HeaderField("X-Trace", "trace-value"),)),
        query=QueryParameters((QueryParameter("region", "east"),)),
        body=TransportBody(
            Bytes(b'{"input":"hello"}'),
            MediaType("application", "json"),
        ),
    )


class _RecordingHandler:
    """Structural handler recording calls and applying bounded replacements."""

    __slots__ = (
        "_apply_error",
        "_apply_inputs",
        "_descriptor",
        "_modes",
        "_mutate",
        "_recorder",
        "_supports_inputs",
    )

    def __init__(
        self,
        modes: frozenset[BodySigningMode],
        recorder: ComponentCallRecorder,
        *,
        mutate: bool = False,
        apply_error: BaseException | None = None,
    ) -> None:
        """Retain configured matching, mutation, and failure behavior."""
        self._descriptor = ComponentDescriptor(
            "Recording authorization handler", "1", "application"
        )
        self._modes = modes
        self._recorder = recorder
        self._mutate = mutate
        self._apply_error = apply_error
        self._supports_inputs: list[tuple[Authorization, BodySigningRequirement]] = []
        self._apply_inputs: list[
            tuple[Authorization, AuthorizationContext, MutableTransportRequest]
        ] = []

    @property
    def descriptor(self) -> ComponentDescriptor:
        """Return valid immutable component metadata."""
        return self._descriptor

    @property
    def supports_inputs(
        self,
    ) -> tuple[tuple[Authorization, BodySigningRequirement], ...]:
        """Return an immutable snapshot of exact matching inputs."""
        return tuple(self._supports_inputs)

    @property
    def apply_inputs(
        self,
    ) -> tuple[
        tuple[Authorization, AuthorizationContext, MutableTransportRequest], ...
    ]:
        """Return an immutable snapshot of exact application inputs."""
        return tuple(self._apply_inputs)

    def supports(
        self,
        authorization: Authorization,
        body_signing_requirement: BodySigningRequirement,
    ) -> frozenset[BodySigningMode]:
        """Record exact matching facts and return configured modes."""
        self._recorder.record("supports")
        self._supports_inputs.append((authorization, body_signing_requirement))
        return self._modes

    async def apply(
        self,
        authorization: Authorization,
        context: AuthorizationContext,
        request: MutableTransportRequest,
    ) -> None:
        """Record exact inputs, optionally replace fields, then return or fail."""
        self._recorder.record("apply")
        self._apply_inputs.append((authorization, context, request))
        if self._mutate:
            # Exercise every Handler-owned replacement while deliberately not
            # changing method, freezing, sending, or exposing a network surface.
            request.replace_url(
                UriValue("https://authorized.example.test/v1/run", True)
            )
            request.replace_headers(
                Headers((HeaderField("Authorization", "fixture-value"),))
            )
            request.replace_query(
                QueryParameters((QueryParameter("signature", "fixture"),))
            )
            request.replace_body(
                TransportBody(
                    Bytes(b"signed-body"),
                    MediaType("application", "octet-stream"),
                )
            )
        if self._apply_error is not None:
            raise self._apply_error
        await asyncio.sleep(0)


class _InvalidSupportsHandler:
    """Return one configured malformed compatibility value."""

    descriptor = ComponentDescriptor("Invalid supports handler", "1", "application")

    def __init__(self, result: object) -> None:
        """Retain the exact malformed dynamic result."""
        self._result = result

    def supports(
        self,
        authorization: Authorization,
        body_signing_requirement: BodySigningRequirement,
    ) -> frozenset[BodySigningMode]:
        """Discard inputs and return the malformed value under a static cast."""
        del authorization, body_signing_requirement
        return cast(frozenset[BodySigningMode], self._result)

    async def apply(
        self,
        authorization: Authorization,
        context: AuthorizationContext,
        request: MutableTransportRequest,
    ) -> None:
        """Provide valid async apply behavior for constructor conformance."""
        del authorization, context, request


class _InvalidApplyResultHandler:
    """Return a non-None dynamic value from asynchronous apply."""

    descriptor = ComponentDescriptor("Invalid apply handler", "1", "application")

    def supports(
        self,
        authorization: Authorization,
        body_signing_requirement: BodySigningRequirement,
    ) -> frozenset[BodySigningMode]:
        """Provide valid compatibility behavior."""
        del authorization, body_signing_requirement
        return frozenset(("none",))

    async def apply(
        self,
        authorization: Authorization,
        context: AuthorizationContext,
        request: MutableTransportRequest,
    ) -> None:
        """Return an invalid value under the declared None annotation."""
        del authorization, context, request
        return cast(None, object())


class _FreezingHandler:
    """Illegally close the Runtime-owned request mutation window."""

    descriptor = ComponentDescriptor("Freezing handler", "1", "application")

    def supports(
        self,
        authorization: Authorization,
        body_signing_requirement: BodySigningRequirement,
    ) -> frozenset[BodySigningMode]:
        """Provide valid compatibility behavior."""
        del authorization, body_signing_requirement
        return frozenset(("none",))

    async def apply(
        self,
        authorization: Authorization,
        context: AuthorizationContext,
        request: MutableTransportRequest,
    ) -> None:
        """Freeze the request to exercise post-apply lifecycle rejection."""
        del authorization, context
        request.freeze()


class _InvalidDescriptorHandler:
    """Expose complete operations with invalid component metadata."""

    descriptor = cast(ComponentDescriptor, object())

    def supports(
        self,
        authorization: Authorization,
        body_signing_requirement: BodySigningRequirement,
    ) -> frozenset[BodySigningMode]:
        """Provide valid compatibility behavior."""
        del authorization, body_signing_requirement
        return frozenset(("none",))

    async def apply(
        self,
        authorization: Authorization,
        context: AuthorizationContext,
        request: MutableTransportRequest,
    ) -> None:
        """Provide valid async application behavior."""
        del authorization, context, request


class _AsyncSupportsHandler:
    """Expose invalid asynchronous compatibility matching."""

    descriptor = ComponentDescriptor("Async supports handler", "1", "application")

    async def supports(
        self,
        authorization: Authorization,
        body_signing_requirement: BodySigningRequirement,
    ) -> frozenset[BodySigningMode]:
        """Return compatibility facts asynchronously."""
        del authorization, body_signing_requirement
        return frozenset(("none",))

    async def apply(
        self,
        authorization: Authorization,
        context: AuthorizationContext,
        request: MutableTransportRequest,
    ) -> None:
        """Provide valid async application behavior."""
        del authorization, context, request


class _SyncApplyHandler:
    """Expose invalid synchronous authorization application."""

    descriptor = ComponentDescriptor("Sync apply handler", "1", "application")

    def supports(
        self,
        authorization: Authorization,
        body_signing_requirement: BodySigningRequirement,
    ) -> frozenset[BodySigningMode]:
        """Provide valid compatibility behavior."""
        del authorization, body_signing_requirement
        return frozenset(("none",))

    def apply(
        self,
        authorization: Authorization,
        context: AuthorizationContext,
        request: MutableTransportRequest,
    ) -> None:
        """Return synchronously instead of exposing the async SPI."""
        del authorization, context, request


def test_suite_validates_exact_supported_modes_with_existing_stub() -> None:
    """Preserve immutable compatibility output without apply side effects."""
    modes: frozenset[BodySigningMode] = frozenset(
        ("precomputed_digest", "buffered_digest")
    )
    handler = StubAuthorizationHandler(
        ComponentDescriptor("Stub handler", "1", "application"),
        modes,
    )
    observed: list[frozenset[BodySigningMode]] = []

    def assert_modes(actual: frozenset[BodySigningMode]) -> None:
        """Require the exact configured immutable mode set."""
        assert actual is modes
        observed.append(actual)

    AuthorizationHandlerContractSuite(handler).assert_supports(
        _authorization(),
        BodySigningRequirement(
            required=True,
            acceptable_modes=("precomputed_digest", "buffered_digest"),
            max_buffer_bytes=1_024,
        ),
        assertion=assert_modes,
    )

    assert observed == [modes]
    assert handler.requests_before == ()
    assert handler.requests_after == ()


def test_suite_accepts_structural_handler_and_preserves_support_inputs() -> None:
    """Require no SDK inheritance and invoke supports exactly once."""
    authorization = _authorization()
    requirement = BodySigningRequirement()
    modes: frozenset[BodySigningMode] = frozenset(("none",))
    recorder = ComponentCallRecorder()
    handler = _RecordingHandler(modes, recorder)

    def assert_identity(actual: frozenset[BodySigningMode]) -> None:
        """Require the exact configured support result."""
        assert actual is modes

    AuthorizationHandlerContractSuite(handler).assert_supports(
        authorization,
        requirement,
        assertion=assert_identity,
    )

    assert recorder.calls == ("supports",)
    assert handler.supports_inputs == ((authorization, requirement),)
    assert handler.supports_inputs[0][0] is authorization
    assert handler.supports_inputs[0][1] is requirement


def test_supports_rejects_mutable_and_invalid_mode_results() -> None:
    """Require an immutable set containing only defined signing modes."""
    invalid_results: tuple[tuple[object, type[BaseException], str], ...] = (
        (set(("none",)), TypeError, "handler supports must return a frozenset."),
        (
            frozenset((cast(BodySigningMode, 1),)),
            TypeError,
            "handler supported modes must contain strings.",
        ),
        (
            frozenset((cast(BodySigningMode, "future_mode"),)),
            ValueError,
            "handler supported modes contains an unsupported mode",
        ),
    )

    def ignore_modes(modes: frozenset[BodySigningMode]) -> None:
        """Provide a callback invalid results must not invoke."""
        del modes

    for result, exception_type, message in invalid_results:
        try:
            AuthorizationHandlerContractSuite(
                _InvalidSupportsHandler(result)
            ).assert_supports(
                _authorization(),
                BodySigningRequirement(),
                assertion=ignore_modes,
            )
        except exception_type as error:
            assert message in str(error)
        else:
            raise AssertionError("Expected malformed supported modes to fail.")


def test_supports_validates_callback_and_inputs_before_handler_call() -> None:
    """Reject malformed matching cases without compatibility side effects."""
    recorder = ComponentCallRecorder()
    suite = AuthorizationHandlerContractSuite(
        _RecordingHandler(frozenset(("none",)), recorder)
    )

    async def async_assertion(modes: frozenset[BodySigningMode]) -> None:
        """Provide an invalid coroutine compatibility callback."""
        del modes

    invalid_assertions = (
        cast(Callable[[frozenset[BodySigningMode]], None], object()),
        cast(Callable[[frozenset[BodySigningMode]], None], async_assertion),
    )
    for assertion in invalid_assertions:
        try:
            suite.assert_supports(
                _authorization(),
                BodySigningRequirement(),
                assertion=assertion,
            )
        except TypeError:
            pass
        else:
            raise AssertionError("Expected invalid supports callback to fail.")

    def ignore_modes(modes: frozenset[BodySigningMode]) -> None:
        """Provide a valid callback malformed inputs must not invoke."""
        del modes

    invalid_inputs: tuple[
        tuple[Authorization, BodySigningRequirement, str],
        ...,
    ] = (
        (
            cast(Authorization, object()),
            BodySigningRequirement(),
            "authorization must implement Authorization.",
        ),
        (
            _Authorization(cast(OpenIdentifier, object())),
            BodySigningRequirement(),
            "authorization kind must be an OpenIdentifier.",
        ),
        (
            _authorization(),
            cast(BodySigningRequirement, object()),
            "body_signing_requirement must be a BodySigningRequirement.",
        ),
    )
    for authorization, requirement, message in invalid_inputs:
        try:
            suite.assert_supports(
                authorization,
                requirement,
                assertion=ignore_modes,
            )
        except TypeError as error:
            assert str(error) == message
        else:
            raise AssertionError("Expected invalid supports input to fail.")

    assert recorder.calls == ()


def test_suite_validates_all_permitted_request_replacements() -> None:
    """Expose exact apply inputs and bounded URL/header/query/body changes."""

    async def scenario() -> None:
        """Run one structural mutating handler through the async contract."""
        authorization = _authorization()
        context = _context()
        request = _request()
        recorder = ComponentCallRecorder()
        handler = _RecordingHandler(
            frozenset(("none",)),
            recorder,
            mutate=True,
        )
        observed: list[MutableTransportRequest] = []

        def assert_request(actual: MutableTransportRequest) -> None:
            """Verify exact request identity and every permitted replacement."""
            assert actual is request
            assert actual.method == "POST"
            assert actual.url.value == "https://authorized.example.test/v1/run"
            assert actual.headers.get_all("Authorization") == ("fixture-value",)
            assert actual.query.values[0].name == "signature"
            assert actual.body.bytes == b"signed-body"
            assert actual.is_frozen is False
            observed.append(actual)

        await AuthorizationHandlerContractSuite(handler).assert_apply(
            authorization,
            context,
            request,
            assertion=assert_request,
        )

        assert observed == [request]
        assert recorder.calls == ("apply",)
        assert handler.apply_inputs == ((authorization, context, request),)
        assert not hasattr(handler, "send")

    asyncio.run(scenario())


def test_suite_validates_existing_stub_noop_apply_boundary() -> None:
    """Keep an unchanged request open across the existing no-op Stub."""

    async def scenario() -> None:
        """Inspect Stub before/after snapshots through the public suite."""
        handler = StubAuthorizationHandler(
            ComponentDescriptor("Stub handler", "1", "application"),
            frozenset(("none",)),
        )
        request = _request()

        def assert_request(actual: MutableTransportRequest) -> None:
            """Require unchanged open request state after no-op authorization."""
            assert actual is request
            assert actual.is_frozen is False
            assert actual.headers.get_all("Authorization") == ()

        await AuthorizationHandlerContractSuite(handler).assert_apply(
            _authorization(),
            _context(),
            request,
            assertion=assert_request,
        )

        assert len(handler.requests_before) == 1
        assert len(handler.requests_after) == 1
        assert handler.requests_before[0] == handler.requests_after[0]

    asyncio.run(scenario())


def test_suite_preserves_exact_apply_failure_and_open_request() -> None:
    """Expose exact failure after bounded mutation without freezing."""

    async def scenario() -> None:
        """Run a failing structural handler and inspect terminal request state."""
        failure = RuntimeError("credential provider failed")
        request = _request()
        handler = _RecordingHandler(
            frozenset(("none",)),
            ComponentCallRecorder(),
            mutate=True,
            apply_error=failure,
        )
        observed: list[BaseException] = []

        def assert_failure(actual: BaseException) -> None:
            """Require exact error and caller-visible bounded partial state."""
            assert actual is failure
            assert request.is_frozen is False
            assert request.headers.get_all("Authorization") == ("fixture-value",)
            observed.append(actual)

        await AuthorizationHandlerContractSuite(handler).assert_apply_failure(
            _authorization(),
            _context(),
            request,
            assertion=assert_failure,
        )

        assert observed == [failure]

    asyncio.run(scenario())


def test_apply_failure_rejects_success_after_one_open_request_call() -> None:
    """Do not invoke the failure callback when apply completes normally."""

    async def scenario() -> None:
        """Run one successful Handler through the negative contract branch."""
        recorder = ComponentCallRecorder()
        handler = _RecordingHandler(frozenset(("none",)), recorder)
        request = _request()
        callback_calls: list[BaseException] = []

        def record_unexpected_failure(error: BaseException) -> None:
            """Record a failure callback invocation that must not occur."""
            callback_calls.append(error)

        try:
            await AuthorizationHandlerContractSuite(handler).assert_apply_failure(
                _authorization(),
                _context(),
                request,
                assertion=record_unexpected_failure,
            )
        except AssertionError as error:
            assert str(error) == "handler apply was expected to fail."
        else:
            raise AssertionError("Expected successful apply to fail negative case.")

        assert recorder.calls == ("apply",)
        assert request.is_frozen is False
        assert callback_calls == []

    asyncio.run(scenario())


def test_apply_rejects_non_none_result_and_handler_owned_freeze() -> None:
    """Enforce async return and Runtime-owned request lifecycle boundaries."""

    async def scenario() -> None:
        """Exercise two dynamically malformed apply implementations."""

        def ignore_request(request: MutableTransportRequest) -> None:
            """Provide a callback malformed apply behavior must not invoke."""
            del request

        try:
            await AuthorizationHandlerContractSuite(
                _InvalidApplyResultHandler()
            ).assert_apply(
                _authorization(),
                _context(),
                _request(),
                assertion=ignore_request,
            )
        except AssertionError as error:
            assert str(error) == "handler apply must return None."
        else:
            raise AssertionError("Expected non-None apply result to fail.")

        frozen_request = _request()
        try:
            await AuthorizationHandlerContractSuite(_FreezingHandler()).assert_apply(
                _authorization(),
                _context(),
                frozen_request,
                assertion=ignore_request,
            )
        except AssertionError as error:
            assert str(error) == "handler must not freeze the request."
        else:
            raise AssertionError("Expected handler-owned freeze to fail.")

        assert frozen_request.is_frozen

    asyncio.run(scenario())


def test_suite_preserves_handler_and_callback_failure_identity() -> None:
    """Propagate independently owned apply failures without translation."""

    async def scenario() -> None:
        """Exercise unexpected Handler and expected-failure callback errors."""
        handler_failure = RuntimeError("authorization failed")
        handler = _RecordingHandler(
            frozenset(("none",)),
            ComponentCallRecorder(),
            apply_error=handler_failure,
        )
        callback_failure = AssertionError("authorization error mismatch")

        def ignore_request(request: MutableTransportRequest) -> None:
            """Provide a callback unexpected Handler failure must prevent."""
            del request

        await _assert_awaitable_raises_identity(
            AuthorizationHandlerContractSuite(handler).assert_apply(
                _authorization(),
                _context(),
                _request(),
                assertion=ignore_request,
            ),
            handler_failure,
        )

        def fail_assertion(error: BaseException) -> None:
            """Confirm Handler error, then raise exact callback failure."""
            assert error is handler_failure
            raise callback_failure

        await _assert_awaitable_raises_identity(
            AuthorizationHandlerContractSuite(handler).assert_apply_failure(
                _authorization(),
                _context(),
                _request(),
                assertion=fail_assertion,
            ),
            callback_failure,
        )

    asyncio.run(scenario())


async def _assert_awaitable_raises_identity(
    awaitable: Awaitable[object],
    expected: BaseException,
) -> None:
    """Await one contract operation and require exact failure identity."""
    try:
        await awaitable
    except BaseException as error:
        assert error is expected
        return
    raise AssertionError(f"Expected {type(expected).__name__} to be raised.")


def test_suite_validates_handler_callbacks_and_apply_inputs_before_calls() -> None:
    """Reject malformed setup and case inputs before Handler behavior."""
    invalid_handlers = (
        cast(AuthorizationHandler, object()),
        cast(AuthorizationHandler, _InvalidDescriptorHandler()),
        cast(AuthorizationHandler, _AsyncSupportsHandler()),
        cast(AuthorizationHandler, _SyncApplyHandler()),
    )
    expected_messages = (
        "handler must implement AuthorizationHandler.",
        "handler descriptor must be a ComponentDescriptor.",
        "handler supports operation must be synchronous.",
        "handler apply operation must be asynchronous.",
    )
    for handler, message in zip(invalid_handlers, expected_messages, strict=True):
        try:
            AuthorizationHandlerContractSuite(handler)
        except TypeError as error:
            assert str(error) == message
        else:
            raise AssertionError("Expected invalid Handler setup to fail.")

    async def scenario() -> None:
        """Validate callbacks and apply inputs without invoking the Handler."""
        recorder = ComponentCallRecorder()
        handler = _RecordingHandler(frozenset(("none",)), recorder)
        suite = AuthorizationHandlerContractSuite(handler)

        async def async_assertion(request: MutableTransportRequest) -> None:
            """Provide an invalid coroutine callback without executing it."""
            del request

        invalid_assertions = (
            cast(Callable[[MutableTransportRequest], None], object()),
            cast(Callable[[MutableTransportRequest], None], async_assertion),
        )
        for assertion in invalid_assertions:
            try:
                await suite.assert_apply(
                    _authorization(),
                    _context(),
                    _request(),
                    assertion=assertion,
                )
            except TypeError:
                pass
            else:
                raise AssertionError("Expected invalid assertion callback to fail.")

        def ignore_request(request: MutableTransportRequest) -> None:
            """Provide a valid callback while testing malformed inputs."""
            del request

        frozen_request = _request()
        frozen_request.freeze()
        invalid_inputs: tuple[
            tuple[Authorization, AuthorizationContext, MutableTransportRequest, str],
            ...,
        ] = (
            (
                cast(Authorization, object()),
                _context(),
                _request(),
                "authorization must implement Authorization.",
            ),
            (
                _Authorization(cast(OpenIdentifier, object())),
                _context(),
                _request(),
                "authorization kind must be an OpenIdentifier.",
            ),
            (
                _authorization(),
                cast(AuthorizationContext, object()),
                _request(),
                "context must be an AuthorizationContext.",
            ),
            (
                _authorization(),
                _context(),
                cast(MutableTransportRequest, object()),
                "request must be a MutableTransportRequest.",
            ),
        )
        for authorization, context, request, message in invalid_inputs:
            try:
                await suite.assert_apply(
                    authorization,
                    context,
                    request,
                    assertion=ignore_request,
                )
            except TypeError as error:
                assert str(error) == message
            else:
                raise AssertionError("Expected invalid apply input to fail.")

        try:
            await suite.assert_apply(
                _authorization(),
                _context(),
                frozen_request,
                assertion=ignore_request,
            )
        except ValueError as error:
            assert str(error) == "request must be open before authorization."
        else:
            raise AssertionError("Expected frozen request setup to fail.")

        assert recorder.calls == ()

    asyncio.run(scenario())


def test_suite_exposes_only_atomic_handler_contract_operations() -> None:
    """Keep exact mixed sync/async surface and exclude adjacent behavior."""
    supports = AuthorizationHandlerContractSuite.assert_supports
    apply = AuthorizationHandlerContractSuite.assert_apply
    failure = AuthorizationHandlerContractSuite.assert_apply_failure

    assert tuple(inspect.signature(supports).parameters) == (
        "self",
        "authorization",
        "body_signing_requirement",
        "assertion",
    )
    expected_apply_parameters = (
        "self",
        "authorization",
        "context",
        "request",
        "assertion",
    )
    assert tuple(inspect.signature(apply).parameters) == expected_apply_parameters
    assert tuple(inspect.signature(failure).parameters) == expected_apply_parameters
    assert get_type_hints(supports) == {
        "authorization": Authorization,
        "body_signing_requirement": BodySigningRequirement,
        "assertion": Callable[[frozenset[BodySigningMode]], None],
        "return": type(None),
    }
    assert get_type_hints(apply) == {
        "authorization": Authorization,
        "context": AuthorizationContext,
        "request": MutableTransportRequest,
        "assertion": Callable[[MutableTransportRequest], None],
        "return": type(None),
    }
    assert get_type_hints(failure) == {
        "authorization": Authorization,
        "context": AuthorizationContext,
        "request": MutableTransportRequest,
        "assertion": Callable[[BaseException], None],
        "return": type(None),
    }
    assert not inspect.iscoroutinefunction(supports)
    assert inspect.iscoroutinefunction(apply)
    assert inspect.iscoroutinefunction(failure)

    suite = AuthorizationHandlerContractSuite(
        StubAuthorizationHandler(
            ComponentDescriptor("Stub handler", "1", "application"),
            frozenset(("none",)),
        )
    )
    for forbidden_member in (
        "load_fixture",
        "resolve_handler",
        "reveal",
        "freeze",
        "send",
        "transport",
        "retry",
        "register",
        "reset",
        "run",
    ):
        assert not hasattr(suite, forbidden_member)
