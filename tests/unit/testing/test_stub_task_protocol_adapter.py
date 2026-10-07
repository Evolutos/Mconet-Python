"""Deterministic outcome tests for StubTaskProtocolAdapter."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import cast

from mconet.core.domain import (
    ArtifactCatalog,
    ErrorCategory,
    Extensions,
    Headers,
    InteractionMode,
    InteractionPhase,
    MediaType,
    ModelInteractionError,
    ModelRequest,
    ModelTarget,
    ModelTaskResult,
    OpenIdentifier,
    OutputStatus,
    ParsedTaskResponse,
    QueryParameters,
    ResolvedServiceAccess,
    TaskDescriptor,
    TaskDocument,
    UriValue,
)
from mconet.core.spi import (
    BodySigningRequirement,
    ComponentDescriptor,
    DecoderSelection,
    EncoderSelection,
    ErasedRuntimeValue,
    ProtocolExecutionPlan,
    ProtocolRequestPlan,
    TaskProtocolAdapter,
    TransportOutcome,
    TransportRequestPlan,
    TransportResponseMetadata,
    TransportSelection,
)
from mconet.testing import StubTaskProtocolAdapter


def _empty_extensions() -> Extensions:
    """Create independent portable mappings for structural result fixtures."""
    # Fresh mappings keep the custom task result isolated while satisfying the
    # complete ModelTaskResult extension surface.
    return {}


@dataclass(frozen=True, slots=True)
class _Authorization:
    """Opaque authorization fixture retained only by the transport plan."""

    kind: OpenIdentifier
    """Open discriminator used later by authorization handler selection."""


@dataclass(frozen=True, slots=True)
class _TaskResult:
    """Complete structural result used by the configured parsed response."""

    descriptor: TaskDescriptor
    """Task contract associated with this result fixture."""

    document: TaskDocument
    """Task-specific response document represented by a typed test sentinel."""

    artifacts: ArtifactCatalog
    """Result-local artifact catalog, empty for this adapter stub test."""

    metadata: Extensions = field(default_factory=_empty_extensions)
    """Portable result metadata required by the structural protocol."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Unknown result fields retained by the structural protocol."""


@dataclass(frozen=True, slots=True)
class _ConfiguredValues:
    """Group exact constructor outputs used across independent method tests."""

    descriptor: ComponentDescriptor
    """Static metadata returned by the stub property."""

    execution_plan: ProtocolExecutionPlan
    """Prebuilt plan returned by prepare_plan."""

    request_plan: ProtocolRequestPlan
    """Prebuilt native request plan returned by build_request."""

    parsed_response: ParsedTaskResponse
    """Prebuilt service facts returned by parse_response."""

    parsed_error: ModelInteractionError
    """Prebuilt normalized mapping returned by parse_error."""


def _values() -> _ConfiguredValues:
    """Create one complete set of exact adapter stub outputs."""
    authorization = _Authorization(OpenIdentifier("authorization.none"))
    transport_plan = TransportRequestPlan(
        endpoint=UriValue("https://models.example.test", True),
        path="/v1/responses",
        method="POST",
        headers=Headers(),
        query=QueryParameters(),
        authorization=authorization,
        body_signing_requirement=BodySigningRequirement(),
    )
    media_type = MediaType("application", "json")
    execution_plan = ProtocolExecutionPlan(
        transport_plan=transport_plan,
        payload_encoder=EncoderSelection(media_type, "protocol.request"),
        success_decoder=DecoderSelection(media_type, "protocol.response"),
        error_decoder=DecoderSelection(media_type, "protocol.error"),
        transport=TransportSelection(OpenIdentifier("http")),
    )
    request_plan = ProtocolRequestPlan(
        ErasedRuntimeValue(OpenIdentifier("protocol.request"), {"input": "hi"}),
        execution_plan,
    )
    result = _TaskResult(
        descriptor=cast(TaskDescriptor, object()),
        document=cast(TaskDocument, object()),
        artifacts=ArtifactCatalog(),
    )
    assert isinstance(result, ModelTaskResult)
    parsed_response = ParsedTaskResponse(
        result=result,
        status=OutputStatus(OpenIdentifier("completed")),
    )
    parsed_error = ModelInteractionError(
        category=ErrorCategory(OpenIdentifier("service")),
        phase=InteractionPhase(OpenIdentifier("response_parsing")),
        code="service_error",
        message="The service returned a configured test error.",
    )

    # Every value is nominally complete before reaching Stub construction, so
    # method tests isolate configured behavior instead of invalid fixture setup.
    return _ConfiguredValues(
        ComponentDescriptor("Stub adapter", "1", "application"),
        execution_plan,
        request_plan,
        parsed_response,
        parsed_error,
    )


def _stub(
    values: _ConfiguredValues,
    *,
    supports_result: bool = True,
    supports_error: BaseException | None = None,
    prepare_plan_error: BaseException | None = None,
    build_request_error: BaseException | None = None,
    parse_response_error: BaseException | None = None,
    parse_error_error: BaseException | None = None,
) -> StubTaskProtocolAdapter:
    """Build one stub with shared valid returns and selected method failures."""
    # The helper supplies one recognized error result. The dedicated None test
    # invokes production construction directly to cover that distinct outcome.
    return StubTaskProtocolAdapter(
        values.descriptor,
        supports_result=supports_result,
        prepare_plan_result=values.execution_plan,
        build_request_result=values.request_plan,
        parse_response_result=values.parsed_response,
        parse_error_result=values.parsed_error,
        supports_error=supports_error,
        prepare_plan_error=prepare_plan_error,
        build_request_error=build_request_error,
        parse_response_error=parse_response_error,
        parse_error_error=parse_error_error,
    )


def _assert_raises_identity(
    action: Callable[[], object],
    expected: BaseException,
) -> None:
    """Require one method to raise the exact configured exception object."""
    try:
        action()
    except BaseException as error:
        # Identity proves the stub performs no wrapping, normalization, copying,
        # or replacement with a generic test failure.
        assert error is expected
        return
    raise AssertionError(f"Expected {type(expected).__name__} to be raised.")


def test_stub_structurally_implements_task_protocol_adapter() -> None:
    """Expose complete adapter behavior without inheritance or registration."""
    values = _values()
    stub = _stub(values)

    accepted: TaskProtocolAdapter = stub

    # Static and runtime protocol boundaries preserve the exact stub and its
    # immutable descriptor without a component ID or wrapper.
    assert accepted is stub
    assert isinstance(stub, TaskProtocolAdapter)
    assert stub.descriptor is values.descriptor


def test_stub_returns_every_independently_configured_result() -> None:
    """Return exact identities from all five adapter operations."""
    values = _values()
    stub = _stub(values, supports_result=False)
    target = cast(ModelTarget, object())
    task = cast(TaskDescriptor, object())
    mode = cast(InteractionMode, object())
    request = cast(ModelRequest, object())
    access = cast(ResolvedServiceAccess, object())
    response = ErasedRuntimeValue(OpenIdentifier("protocol.response"), object())
    error = ErasedRuntimeValue(OpenIdentifier("protocol.error"), object())
    metadata = TransportResponseMetadata(
        TransportOutcome(OpenIdentifier("service_error")),
        Headers(),
        status_code=400,
    )

    assert stub.supports(target, task, mode) is False
    assert stub.prepare_plan(request, access, mode) is values.execution_plan
    assert stub.build_request(request, values.execution_plan) is values.request_plan
    assert stub.parse_response(response) is values.parsed_response
    assert stub.parse_error(error, metadata) is values.parsed_error


def test_stub_preserves_none_as_a_parse_error_result() -> None:
    """Model an unrecognized error payload without treating None as unset."""
    values = _values()
    stub = StubTaskProtocolAdapter(
        values.descriptor,
        supports_result=True,
        prepare_plan_result=values.execution_plan,
        build_request_result=values.request_plan,
        parse_response_result=values.parsed_response,
        parse_error_result=None,
    )

    result = stub.parse_error(
        ErasedRuntimeValue(OpenIdentifier("protocol.error"), object()),
        TransportResponseMetadata(
            TransportOutcome(OpenIdentifier("service_error")),
            Headers(),
        ),
    )

    # None is the protocol's explicit unrecognized-payload result; it does not
    # select a default ModelInteractionError or trigger the failure path.
    assert result is None


def test_each_stub_method_raises_its_exact_configured_failure() -> None:
    """Keep five fault branches independent and preserve exception identity."""
    values = _values()
    failures: tuple[BaseException, ...] = (
        RuntimeError("supports failed"),
        ValueError("prepare plan failed"),
        LookupError("build request failed"),
        ArithmeticError("parse response failed"),
        KeyboardInterrupt("parse error interrupted"),
    )
    stub = _stub(
        values,
        supports_error=failures[0],
        prepare_plan_error=failures[1],
        build_request_error=failures[2],
        parse_response_error=failures[3],
        parse_error_error=failures[4],
    )
    method_calls: tuple[Callable[[], object], ...] = (
        lambda: stub.supports(
            cast(ModelTarget, object()),
            cast(TaskDescriptor, object()),
            cast(InteractionMode, object()),
        ),
        lambda: stub.prepare_plan(
            cast(ModelRequest, object()),
            cast(ResolvedServiceAccess, object()),
            cast(InteractionMode, object()),
        ),
        lambda: stub.build_request(
            cast(ModelRequest, object()),
            values.execution_plan,
        ),
        lambda: stub.parse_response(
            ErasedRuntimeValue(OpenIdentifier("protocol.response"), object())
        ),
        lambda: stub.parse_error(
            ErasedRuntimeValue(OpenIdentifier("protocol.error"), object()),
            TransportResponseMetadata(
                TransportOutcome(OpenIdentifier("service_error")),
                Headers(),
            ),
        ),
    )

    for action, failure in zip(method_calls, failures, strict=True):
        _assert_raises_identity(action, failure)


def test_one_configured_failure_does_not_change_other_method_results() -> None:
    """Apply one method failure without contaminating independent outcomes."""
    values = _values()
    failure = RuntimeError("planning unavailable")
    stub = _stub(values, prepare_plan_error=failure)

    _assert_raises_identity(
        lambda: stub.prepare_plan(
            cast(ModelRequest, object()),
            cast(ResolvedServiceAccess, object()),
            cast(InteractionMode, object()),
        ),
        failure,
    )

    # Unrelated methods still use their own construction-time results after the
    # failed call; the stub has no shared current-outcome or consumed state.
    assert stub.supports(
        cast(ModelTarget, object()),
        cast(TaskDescriptor, object()),
        cast(InteractionMode, object()),
    )
    assert (
        stub.parse_response(
            ErasedRuntimeValue(OpenIdentifier("protocol.response"), object())
        )
        is values.parsed_response
    )


def test_stub_rejects_invalid_results_and_failures_at_construction() -> None:
    """Fail fast when dynamic tests provide malformed configured outcomes."""
    values = _values()

    invalid_calls: tuple[tuple[Callable[[], object], str], ...] = (
        (
            lambda: StubTaskProtocolAdapter(
                cast(ComponentDescriptor, object()),
                supports_result=True,
                prepare_plan_result=values.execution_plan,
                build_request_result=values.request_plan,
                parse_response_result=values.parsed_response,
                parse_error_result=values.parsed_error,
            ),
            "descriptor must be a ComponentDescriptor",
        ),
        (
            lambda: StubTaskProtocolAdapter(
                values.descriptor,
                supports_result=cast(bool, 1),
                prepare_plan_result=values.execution_plan,
                build_request_result=values.request_plan,
                parse_response_result=values.parsed_response,
                parse_error_result=values.parsed_error,
            ),
            "supports_result must be a bool",
        ),
        (
            lambda: StubTaskProtocolAdapter(
                values.descriptor,
                supports_result=True,
                prepare_plan_result=cast(ProtocolExecutionPlan, object()),
                build_request_result=values.request_plan,
                parse_response_result=values.parsed_response,
                parse_error_result=values.parsed_error,
            ),
            "prepare_plan_result must be a ProtocolExecutionPlan",
        ),
        (
            lambda: StubTaskProtocolAdapter(
                values.descriptor,
                supports_result=True,
                prepare_plan_result=values.execution_plan,
                build_request_result=cast(ProtocolRequestPlan, object()),
                parse_response_result=values.parsed_response,
                parse_error_result=values.parsed_error,
            ),
            "build_request_result must be a ProtocolRequestPlan",
        ),
        (
            lambda: StubTaskProtocolAdapter(
                values.descriptor,
                supports_result=True,
                prepare_plan_result=values.execution_plan,
                build_request_result=values.request_plan,
                parse_response_result=cast(ParsedTaskResponse, object()),
                parse_error_result=values.parsed_error,
            ),
            "parse_response_result must be a ParsedTaskResponse",
        ),
        (
            lambda: StubTaskProtocolAdapter(
                values.descriptor,
                supports_result=True,
                prepare_plan_result=values.execution_plan,
                build_request_result=values.request_plan,
                parse_response_result=values.parsed_response,
                parse_error_result=cast(ModelInteractionError, object()),
            ),
            "parse_error_result must be a ModelInteractionError or None",
        ),
        (
            lambda: StubTaskProtocolAdapter(
                values.descriptor,
                supports_result=True,
                prepare_plan_result=values.execution_plan,
                build_request_result=values.request_plan,
                parse_response_result=values.parsed_response,
                parse_error_result=values.parsed_error,
                supports_error=cast(BaseException, "failure"),
            ),
            "supports_error must be a BaseException or None",
        ),
    )

    for action, message in invalid_calls:
        try:
            action()
        except TypeError as error:
            # Stable diagnostics identify the exact misconfigured method outcome
            # instead of deferring a cast failure to an unrelated test action.
            assert message in str(error)
        else:
            raise AssertionError("Expected invalid Stub configuration to fail.")


def test_stub_matches_adapter_surface_without_call_recording_controls() -> None:
    """Expose only adapter behavior and construction-time configuration."""
    values = _values()
    stub = _stub(values)
    expected_parameters = {
        "supports": ("self", "target", "task", "mode"),
        "prepare_plan": ("self", "request", "access", "mode"),
        "build_request": ("self", "request", "plan"),
        "parse_response": ("self", "response"),
        "parse_error": ("self", "error", "metadata"),
    }

    for method_name, parameters in expected_parameters.items():
        method = getattr(StubTaskProtocolAdapter, method_name)
        # The concrete stub preserves the exact synchronous SPI surface instead
        # of adding generic *args, runtime stage names, or async wrappers.
        assert tuple(inspect.signature(method).parameters) == parameters
        assert not inspect.iscoroutinefunction(method)

    # Call recording and post-construction configure methods belong to later,
    # separately scoped test-kit components rather than this behavior stub.
    assert not hasattr(stub, "calls")
    assert not hasattr(stub, "configure")
    assert not hasattr(stub, "reset")
