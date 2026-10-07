"""Branch and boundary tests for AuthorizationHandlerResolverContractSuite."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass
from typing import cast, get_type_hints

from mconet.core.domain import (
    Authorization,
    ErrorCategory,
    InteractionPhase,
    ModelInteractionError,
    OpenIdentifier,
)
from mconet.core.spi import (
    AuthorizationContext,
    AuthorizationHandler,
    AuthorizationHandlerResolver,
    BodySigningMode,
    BodySigningRequirement,
    ComponentDescriptor,
    MutableTransportRequest,
    ResolvedAuthorizationHandler,
)
from mconet.testing import (
    AuthorizationHandlerResolverContractSuite,
    ComponentCallRecorder,
    StubAuthorizationHandlerResolver,
)


@dataclass(frozen=True, slots=True)
class _Authorization:
    """Opaque authorization fixture containing no credential material."""

    kind: OpenIdentifier
    """Non-sensitive mechanism identifier visible during selection."""


class _Handler:
    """Complete handler candidate with observable compatibility calls."""

    __slots__ = ("_descriptor", "_modes", "_supports_calls")

    def __init__(
        self,
        name: str,
        modes: frozenset[BodySigningMode] = frozenset(("none",)),
    ) -> None:
        """Retain metadata and one fixed compatible signing-mode set."""
        self._descriptor = ComponentDescriptor(name, "1", "application")
        self._modes = modes
        self._supports_calls = 0

    @property
    def descriptor(self) -> ComponentDescriptor:
        """Return valid immutable component metadata."""
        return self._descriptor

    @property
    def supports_calls(self) -> int:
        """Return how often compatibility behavior was invoked."""
        return self._supports_calls

    def supports(
        self,
        authorization: Authorization,
        body_signing_requirement: BodySigningRequirement,
    ) -> frozenset[BodySigningMode]:
        """Record one compatibility query and return fixed modes."""
        del authorization, body_signing_requirement
        self._supports_calls += 1
        return self._modes

    async def apply(
        self,
        authorization: Authorization,
        context: AuthorizationContext,
        request: MutableTransportRequest,
    ) -> None:
        """Provide complete no-op async application behavior."""
        del authorization, context, request


def _authorization() -> _Authorization:
    """Build one non-sensitive opaque authorization value."""
    return _Authorization(OpenIdentifier("authorization.fixture"))


def _selection(
    handler: AuthorizationHandler,
    mode: BodySigningMode = "none",
) -> ResolvedAuthorizationHandler:
    """Build one exact handler and signing-mode selection."""
    return ResolvedAuthorizationHandler(handler, mode)


def _resolution_error(code: str) -> ModelInteractionError:
    """Build one normalized authorization resolution failure."""
    return ModelInteractionError(
        ErrorCategory(OpenIdentifier("authentication")),
        InteractionPhase(OpenIdentifier("authorization_resolution")),
        code,
        "Authorization handler resolution failed.",
    )


class _RecordingResolver:
    """Structural resolver recording exact inputs and one configured outcome."""

    __slots__ = ("_calls", "_descriptor", "_error", "_recorder", "_result")

    def __init__(
        self,
        result: ResolvedAuthorizationHandler,
        recorder: ComponentCallRecorder,
        *,
        error: BaseException | None = None,
    ) -> None:
        """Retain exact outcome and initialize ordered call evidence."""
        self._descriptor = ComponentDescriptor(
            "Recording authorization resolver", "1", "application"
        )
        self._result = result
        self._recorder = recorder
        self._error = error
        self._calls: list[
            tuple[
                Authorization,
                BodySigningRequirement,
                tuple[AuthorizationHandler, ...],
            ]
        ] = []

    @property
    def descriptor(self) -> ComponentDescriptor:
        """Return valid immutable component metadata."""
        return self._descriptor

    @property
    def calls(
        self,
    ) -> tuple[
        tuple[
            Authorization,
            BodySigningRequirement,
            tuple[AuthorizationHandler, ...],
        ],
        ...,
    ]:
        """Return an immutable snapshot of exact resolver inputs."""
        return tuple(self._calls)

    def resolve(
        self,
        authorization: Authorization,
        body_signing_requirement: BodySigningRequirement,
        handlers: tuple[AuthorizationHandler, ...],
    ) -> ResolvedAuthorizationHandler:
        """Record exact inputs, then return or raise the configured outcome."""
        self._recorder.record("resolve_authorization_handler")
        self._calls.append((authorization, body_signing_requirement, handlers))
        if self._error is not None:
            raise self._error
        return self._result


class _MalformedResultResolver:
    """Claim the resolver signature while returning an invalid value."""

    descriptor = ComponentDescriptor("Malformed resolver", "1", "application")

    def resolve(
        self,
        authorization: Authorization,
        body_signing_requirement: BodySigningRequirement,
        handlers: tuple[AuthorizationHandler, ...],
    ) -> ResolvedAuthorizationHandler:
        """Discard selection facts and expose malformed implementation output."""
        del authorization, body_signing_requirement, handlers
        return cast(ResolvedAuthorizationHandler, object())


class _InvalidDescriptorResolver:
    """Expose complete resolve behavior with invalid component metadata."""

    descriptor = cast(ComponentDescriptor, object())

    def resolve(
        self,
        authorization: Authorization,
        body_signing_requirement: BodySigningRequirement,
        handlers: tuple[AuthorizationHandler, ...],
    ) -> ResolvedAuthorizationHandler:
        """Return the first candidate so descriptor validation remains isolated."""
        del authorization, body_signing_requirement
        return _selection(handlers[0])


class _AsyncResolver:
    """Expose an invalid asynchronous resolver operation."""

    descriptor = ComponentDescriptor("Async resolver", "1", "application")

    async def resolve(
        self,
        authorization: Authorization,
        body_signing_requirement: BodySigningRequirement,
        handlers: tuple[AuthorizationHandler, ...],
    ) -> ResolvedAuthorizationHandler:
        """Return the first candidate asynchronously to exercise rejection."""
        del authorization, body_signing_requirement
        return _selection(handlers[0])


class _InvalidHandlerDescriptor:
    """Implement handler operations while exposing invalid metadata."""

    descriptor = cast(ComponentDescriptor, object())

    def supports(
        self,
        authorization: Authorization,
        body_signing_requirement: BodySigningRequirement,
    ) -> frozenset[BodySigningMode]:
        """Return one mode so only descriptor validation is malformed."""
        del authorization, body_signing_requirement
        return frozenset(("none",))

    async def apply(
        self,
        authorization: Authorization,
        context: AuthorizationContext,
        request: MutableTransportRequest,
    ) -> None:
        """Provide complete no-op async application behavior."""
        del authorization, context, request


def test_suite_validates_exact_unique_selection_with_existing_stub() -> None:
    """Preserve selected candidate, mode, result, and zero handler calls."""
    first = _Handler("First handler")
    selected = _Handler("Selected handler")
    handlers: tuple[AuthorizationHandler, ...] = (first, selected)
    expected = _selection(selected)
    resolver = StubAuthorizationHandlerResolver(
        ComponentDescriptor("Stub resolver", "1", "application"),
        expected,
    )
    observed: list[ResolvedAuthorizationHandler] = []

    def assert_selection(actual: ResolvedAuthorizationHandler) -> None:
        """Require exact result, selected candidate, and signing mode."""
        assert actual is expected
        assert actual.handler is selected
        assert actual.body_signing_mode == "none"
        observed.append(actual)

    AuthorizationHandlerResolverContractSuite(resolver).assert_unique_match(
        _authorization(),
        BodySigningRequirement(),
        handlers,
        assertion=assert_selection,
    )

    assert observed == [expected]
    assert first.supports_calls == 0
    assert selected.supports_calls == 0


def test_suite_accepts_structural_resolver_and_preserves_all_inputs() -> None:
    """Require no SDK inheritance and invoke resolution exactly once."""
    authorization = _authorization()
    requirement = BodySigningRequirement()
    selected = _Handler("Selected handler")
    handlers: tuple[AuthorizationHandler, ...] = (selected,)
    expected = _selection(selected)
    recorder = ComponentCallRecorder()
    resolver = _RecordingResolver(expected, recorder)

    def assert_identity(actual: ResolvedAuthorizationHandler) -> None:
        """Require the exact configured unique selection."""
        assert actual is expected

    AuthorizationHandlerResolverContractSuite(resolver).assert_unique_match(
        authorization,
        requirement,
        handlers,
        assertion=assert_identity,
    )

    assert recorder.calls == ("resolve_authorization_handler",)
    assert resolver.calls == ((authorization, requirement, handlers),)
    assert resolver.calls[0][0] is authorization
    assert resolver.calls[0][1] is requirement
    assert resolver.calls[0][2] is handlers


def test_suite_validates_no_match_failure_without_fallback() -> None:
    """Expose exact missing-match failure and preserve an empty candidate set."""
    unused = _Handler("Unused handler")
    failure = _resolution_error("unsupported_authorization")
    resolver = StubAuthorizationHandlerResolver(
        ComponentDescriptor("Stub resolver", "1", "application"),
        _selection(unused),
        error=failure,
    )
    observed: list[BaseException] = []

    def assert_failure(actual: BaseException) -> None:
        """Require exact failure identity and stable no-match code."""
        assert actual is failure
        assert isinstance(actual, ModelInteractionError)
        assert actual.code == "unsupported_authorization"
        observed.append(actual)

    AuthorizationHandlerResolverContractSuite(resolver).assert_no_match(
        _authorization(),
        BodySigningRequirement(),
        (),
        assertion=assert_failure,
    )

    assert observed == [failure]


def test_suite_validates_ambiguous_match_failure_without_order_selection() -> None:
    """Expose exact ambiguity when multiple candidates are compatible."""
    first = _Handler("First handler")
    second = _Handler("Second handler")
    failure = _resolution_error("ambiguous_authorization_handler")
    resolver = StubAuthorizationHandlerResolver(
        ComponentDescriptor("Stub resolver", "1", "application"),
        _selection(first),
        error=failure,
    )

    def assert_failure(actual: BaseException) -> None:
        """Require exact failure identity and stable ambiguity code."""
        assert actual is failure
        assert isinstance(actual, ModelInteractionError)
        assert actual.code == "ambiguous_authorization_handler"

    AuthorizationHandlerResolverContractSuite(resolver).assert_ambiguous_match(
        _authorization(),
        BodySigningRequirement(),
        (first, second),
        assertion=assert_failure,
    )

    assert first.supports_calls == 0
    assert second.supports_calls == 0


def test_unique_match_rejects_external_handler_and_disallowed_mode() -> None:
    """Keep selection inside the candidate and protocol requirement snapshot."""
    candidate = _Handler("Candidate handler")
    external = _Handler(
        "External handler",
        frozenset(("precomputed_digest",)),
    )
    requirement = BodySigningRequirement(
        required=True,
        acceptable_modes=("precomputed_digest",),
    )
    callback_calls: list[ResolvedAuthorizationHandler] = []

    def record_unexpected_selection(result: ResolvedAuthorizationHandler) -> None:
        """Record a callback invocation invalid results must prevent."""
        callback_calls.append(result)

    external_resolver = StubAuthorizationHandlerResolver(
        ComponentDescriptor("External resolver", "1", "application"),
        _selection(external, "precomputed_digest"),
    )
    try:
        AuthorizationHandlerResolverContractSuite(
            external_resolver
        ).assert_unique_match(
            _authorization(),
            requirement,
            (candidate,),
            assertion=record_unexpected_selection,
        )
    except AssertionError as error:
        assert str(error) == (
            "resolver must select a handler from the supplied candidates."
        )
    else:
        raise AssertionError("Expected external handler selection to fail.")

    incompatible_resolver = StubAuthorizationHandlerResolver(
        ComponentDescriptor("Incompatible resolver", "1", "application"),
        _selection(candidate, "none"),
    )
    try:
        AuthorizationHandlerResolverContractSuite(
            incompatible_resolver
        ).assert_unique_match(
            _authorization(),
            requirement,
            (candidate,),
            assertion=record_unexpected_selection,
        )
    except AssertionError as error:
        assert str(error) == (
            "resolver must select a mode accepted by the signing requirement."
        )
    else:
        raise AssertionError("Expected disallowed signing mode to fail.")

    assert callback_calls == []


def test_unique_match_rejects_malformed_dynamic_result() -> None:
    """Require the nominal resolution result before caller assertions."""
    handler = _Handler("Candidate handler")
    callback_calls: list[ResolvedAuthorizationHandler] = []

    def record_unexpected_selection(result: ResolvedAuthorizationHandler) -> None:
        """Record a callback invocation malformed output must prevent."""
        callback_calls.append(result)

    try:
        AuthorizationHandlerResolverContractSuite(
            _MalformedResultResolver()
        ).assert_unique_match(
            _authorization(),
            BodySigningRequirement(),
            (handler,),
            assertion=record_unexpected_selection,
        )
    except AssertionError as error:
        assert str(error) == ("resolver must return a ResolvedAuthorizationHandler.")
    else:
        raise AssertionError("Expected malformed resolver output to fail.")

    assert callback_calls == []


def test_failure_branches_reject_unexpected_selection_after_one_call() -> None:
    """Prevent fallback and order selection from satisfying failure cases."""
    first = _Handler("First handler")
    second = _Handler("Second handler")
    recorder = ComponentCallRecorder()
    resolver = _RecordingResolver(_selection(first), recorder)
    callback_calls: list[BaseException] = []

    def record_unexpected_failure(error: BaseException) -> None:
        """Record a failure callback invocation that must not occur."""
        callback_calls.append(error)

    suite = AuthorizationHandlerResolverContractSuite(resolver)
    try:
        suite.assert_no_match(
            _authorization(),
            BodySigningRequirement(),
            (first,),
            assertion=record_unexpected_failure,
        )
    except AssertionError as error:
        assert str(error) == ("resolver was expected to find no compatible handler.")
    else:
        raise AssertionError("Expected fallback selection to fail no-match case.")

    try:
        suite.assert_ambiguous_match(
            _authorization(),
            BodySigningRequirement(),
            (first, second),
            assertion=record_unexpected_failure,
        )
    except AssertionError as error:
        assert str(error) == ("resolver was expected to reject ambiguous handlers.")
    else:
        raise AssertionError("Expected order selection to fail ambiguity case.")

    assert recorder.calls == (
        "resolve_authorization_handler",
        "resolve_authorization_handler",
    )
    assert callback_calls == []


def test_suite_preserves_resolver_and_assertion_failure_identity() -> None:
    """Propagate independently owned failures without translation."""
    handler = _Handler("Candidate handler")
    resolver_failure = RuntimeError("unexpected resolver failure")
    resolver = _RecordingResolver(
        _selection(handler),
        ComponentCallRecorder(),
        error=resolver_failure,
    )
    assertion_failure = AssertionError("resolution error mismatch")
    unexpected_selections: list[ResolvedAuthorizationHandler] = []

    def record_unexpected_selection(result: ResolvedAuthorizationHandler) -> None:
        """Record a selection callback that resolver failure must prevent."""
        unexpected_selections.append(result)

    def fail_assertion(error: BaseException) -> None:
        """Confirm the resolver error, then raise exact callback failure."""
        assert error is resolver_failure
        raise assertion_failure

    try:
        AuthorizationHandlerResolverContractSuite(resolver).assert_unique_match(
            _authorization(),
            BodySigningRequirement(),
            (handler,),
            assertion=record_unexpected_selection,
        )
    except RuntimeError as error:
        assert error is resolver_failure
    else:
        raise AssertionError("Expected unique-match resolver failure.")

    try:
        AuthorizationHandlerResolverContractSuite(resolver).assert_no_match(
            _authorization(),
            BodySigningRequirement(),
            (handler,),
            assertion=fail_assertion,
        )
    except AssertionError as error:
        assert error is assertion_failure
    else:
        raise AssertionError("Expected assertion callback failure.")

    assert unexpected_selections == []


def test_suite_validates_setup_and_callbacks_before_resolution() -> None:
    """Reject malformed resolver, case inputs, and callbacks before calls."""
    invalid_resolvers = (
        cast(AuthorizationHandlerResolver, object()),
        cast(AuthorizationHandlerResolver, _InvalidDescriptorResolver()),
        cast(AuthorizationHandlerResolver, _AsyncResolver()),
    )
    expected_messages = (
        "resolver must implement AuthorizationHandlerResolver.",
        "resolver descriptor must be a ComponentDescriptor.",
        "resolver operation must be synchronous.",
    )
    for resolver, message in zip(invalid_resolvers, expected_messages, strict=True):
        try:
            AuthorizationHandlerResolverContractSuite(resolver)
        except TypeError as error:
            assert str(error) == message
        else:
            raise AssertionError("Expected invalid resolver setup to fail.")

    handler = _Handler("Candidate handler")
    recorder = ComponentCallRecorder()
    suite = AuthorizationHandlerResolverContractSuite(
        _RecordingResolver(_selection(handler), recorder)
    )

    async def async_assertion(result: ResolvedAuthorizationHandler) -> None:
        """Provide an invalid coroutine callback without executing it."""
        del result

    invalid_assertions = (
        cast(Callable[[ResolvedAuthorizationHandler], None], object()),
        cast(Callable[[ResolvedAuthorizationHandler], None], async_assertion),
    )
    for assertion in invalid_assertions:
        try:
            suite.assert_unique_match(
                _authorization(),
                BodySigningRequirement(),
                (handler,),
                assertion=assertion,
            )
        except TypeError:
            pass
        else:
            raise AssertionError("Expected invalid assertion callback to fail.")

    def ignore_selection(result: ResolvedAuthorizationHandler) -> None:
        """Provide a valid callback while testing case preconditions."""
        del result

    def ignore_failure(error: BaseException) -> None:
        """Provide a valid failure callback while testing preconditions."""
        del error

    try:
        suite.assert_unique_match(
            _authorization(),
            BodySigningRequirement(),
            (),
            assertion=ignore_selection,
        )
    except ValueError as error:
        assert str(error) == "contract case requires at least 1 handler candidates."
    else:
        raise AssertionError("Expected empty unique-match candidates to fail.")

    try:
        suite.assert_ambiguous_match(
            _authorization(),
            BodySigningRequirement(),
            (handler,),
            assertion=ignore_failure,
        )
    except ValueError as error:
        assert str(error) == "contract case requires at least 2 handler candidates."
    else:
        raise AssertionError("Expected one ambiguity candidate to fail.")

    try:
        suite.assert_ambiguous_match(
            _authorization(),
            BodySigningRequirement(),
            (handler,),
            assertion=cast(Callable[[BaseException], None], object()),
        )
    except TypeError:
        pass
    else:
        raise AssertionError("Expected invalid ambiguity callback to fail.")

    assert recorder.calls == ()


def test_suite_rejects_invalid_case_inputs_before_resolution() -> None:
    """Validate opaque authorization, requirement, and every candidate shape."""
    handler = _Handler("Candidate handler")
    recorder = ComponentCallRecorder()
    suite = AuthorizationHandlerResolverContractSuite(
        _RecordingResolver(_selection(handler), recorder)
    )

    def ignore_failure(error: BaseException) -> None:
        """Provide a valid callback that malformed inputs must not invoke."""
        del error

    invalid_cases: tuple[
        tuple[
            Authorization,
            BodySigningRequirement,
            tuple[AuthorizationHandler, ...],
            str,
        ],
        ...,
    ] = (
        (
            cast(Authorization, object()),
            BodySigningRequirement(),
            (),
            "authorization must implement Authorization.",
        ),
        (
            _Authorization(cast(OpenIdentifier, object())),
            BodySigningRequirement(),
            (),
            "authorization kind must be an OpenIdentifier.",
        ),
        (
            _authorization(),
            cast(BodySigningRequirement, object()),
            (),
            "body_signing_requirement must be a BodySigningRequirement.",
        ),
        (
            _authorization(),
            BodySigningRequirement(),
            cast(tuple[AuthorizationHandler, ...], []),
            "handlers must be a tuple.",
        ),
        (
            _authorization(),
            BodySigningRequirement(),
            (cast(AuthorizationHandler, object()),),
            "handlers must contain AuthorizationHandler values.",
        ),
        (
            _authorization(),
            BodySigningRequirement(),
            (_InvalidHandlerDescriptor(),),
            "handler descriptor must be a ComponentDescriptor.",
        ),
    )

    for authorization, requirement, handlers, message in invalid_cases:
        try:
            suite.assert_no_match(
                authorization,
                requirement,
                handlers,
                assertion=ignore_failure,
            )
        except TypeError as error:
            assert str(error) == message
        else:
            raise AssertionError("Expected invalid resolver case input to fail.")

    assert recorder.calls == ()


def test_suite_exposes_only_atomic_resolver_contract_operations() -> None:
    """Keep exact sync signatures and exclude adjacent authorization behavior."""
    unique = AuthorizationHandlerResolverContractSuite.assert_unique_match
    none = AuthorizationHandlerResolverContractSuite.assert_no_match
    ambiguous = AuthorizationHandlerResolverContractSuite.assert_ambiguous_match

    expected_parameters = (
        "self",
        "authorization",
        "body_signing_requirement",
        "handlers",
        "assertion",
    )
    for method in (unique, none, ambiguous):
        assert tuple(inspect.signature(method).parameters) == expected_parameters
        assert not inspect.iscoroutinefunction(method)

    assert get_type_hints(unique) == {
        "authorization": Authorization,
        "body_signing_requirement": BodySigningRequirement,
        "handlers": tuple[AuthorizationHandler, ...],
        "assertion": Callable[[ResolvedAuthorizationHandler], None],
        "return": type(None),
    }
    failure_annotations = {
        "authorization": Authorization,
        "body_signing_requirement": BodySigningRequirement,
        "handlers": tuple[AuthorizationHandler, ...],
        "assertion": Callable[[BaseException], None],
        "return": type(None),
    }
    assert get_type_hints(none) == failure_annotations
    assert get_type_hints(ambiguous) == failure_annotations

    handler = _Handler("Candidate handler")
    suite = AuthorizationHandlerResolverContractSuite(
        StubAuthorizationHandlerResolver(
            ComponentDescriptor("Stub resolver", "1", "application"),
            _selection(handler),
        )
    )
    for forbidden_member in (
        "load_fixture",
        "match",
        "supports",
        "reveal",
        "resolve_credential",
        "authorize",
        "apply",
        "send",
        "register",
        "reset",
        "run",
    ):
        assert not hasattr(suite, forbidden_member)
