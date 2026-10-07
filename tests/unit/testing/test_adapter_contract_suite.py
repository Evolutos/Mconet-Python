"""Reusable behavior and boundary tests for AdapterContractSuite."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TypeVar, cast

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
from mconet.testing import (
    AdapterContractSuite,
    ComponentCallRecorder,
    StubTaskProtocolAdapter,
)

_ValueT = TypeVar("_ValueT")
_DEFAULT_PARSE_ERROR = object()


def _empty_extensions() -> Extensions:
    """Create independent portable extension mappings for result fixtures."""
    return {}


@dataclass(frozen=True, slots=True)
class _Authorization:
    """Provide one opaque authorization marker for a transport plan."""

    kind: OpenIdentifier


@dataclass(frozen=True, slots=True)
class _TaskResult:
    """Provide the complete structural ModelTaskResult test surface."""

    descriptor: TaskDescriptor
    document: TaskDocument
    artifacts: ArtifactCatalog
    metadata: Extensions = field(default_factory=_empty_extensions)
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _Values:
    """Group reusable adapter results for independent contract cases."""

    descriptor: ComponentDescriptor
    execution_plan: ProtocolExecutionPlan
    request_plan: ProtocolRequestPlan
    parsed_response: ParsedTaskResponse
    parsed_error: ModelInteractionError


def _values() -> _Values:
    """Build one complete set of nominal adapter result values."""
    transport_plan = TransportRequestPlan(
        endpoint=UriValue("https://models.example.test", True),
        path="/v1/responses",
        method="POST",
        headers=Headers(),
        query=QueryParameters(),
        authorization=_Authorization(OpenIdentifier("authorization.none")),
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
        ErasedRuntimeValue(OpenIdentifier("protocol.request"), {"input": "hello"}),
        execution_plan,
    )
    task_result = _TaskResult(
        descriptor=cast(TaskDescriptor, object()),
        document=cast(TaskDocument, object()),
        artifacts=ArtifactCatalog(),
    )
    assert isinstance(task_result, ModelTaskResult)
    parsed_response = ParsedTaskResponse(
        task_result,
        OutputStatus(OpenIdentifier("completed")),
    )
    parsed_error = ModelInteractionError(
        ErrorCategory(OpenIdentifier("service")),
        InteractionPhase(OpenIdentifier("response_parsing")),
        "service_error",
        "The service returned a contract fixture error.",
    )
    return _Values(
        ComponentDescriptor("Contract adapter", "1", "application"),
        execution_plan,
        request_plan,
        parsed_response,
        parsed_error,
    )


def _stub(
    values: _Values,
    *,
    parse_error_result: object = _DEFAULT_PARSE_ERROR,
    supports_error: BaseException | None = None,
) -> StubTaskProtocolAdapter:
    """Build one conforming configurable adapter for suite tests."""
    # A private sentinel lets callers select protocol-significant None without
    # confusing it with the helper's default recognized error fixture.
    configured_error = (
        values.parsed_error
        if parse_error_result is _DEFAULT_PARSE_ERROR
        else cast(ModelInteractionError | None, parse_error_result)
    )
    return StubTaskProtocolAdapter(
        values.descriptor,
        supports_result=True,
        prepare_plan_result=values.execution_plan,
        build_request_result=values.request_plan,
        parse_response_result=values.parsed_response,
        parse_error_result=configured_error,
        supports_error=supports_error,
    )


def _identity_assertion(expected: _ValueT) -> Callable[[_ValueT], None]:
    """Create a callback requiring the exact configured result instance."""

    def assert_identity(actual: _ValueT) -> None:
        """Assert result identity without protocol-specific reconstruction."""
        assert actual is expected

    return assert_identity


def _successful_response() -> ErasedRuntimeValue:
    """Create one decoded success payload wrapper for parse contract cases."""
    return ErasedRuntimeValue(
        OpenIdentifier("protocol.response"),
        {"status": "completed"},
    )


def _error_response() -> ErasedRuntimeValue:
    """Create one decoded error payload wrapper for parse contract cases."""
    return ErasedRuntimeValue(
        OpenIdentifier("protocol.error"),
        {"error": "unavailable"},
    )


def _error_metadata() -> TransportResponseMetadata:
    """Create one normalized service-error transport metadata fixture."""
    return TransportResponseMetadata(
        TransportOutcome(OpenIdentifier("service_error")),
        Headers(),
        status_code=503,
    )


class _RecordingAdapter:
    """Custom structural adapter recording every suite invocation."""

    __slots__ = ("_recorder", "_values")

    def __init__(self, values: _Values, recorder: ComponentCallRecorder) -> None:
        """Retain exact outcomes and external call evidence."""
        self._values = values
        self._recorder = recorder

    @property
    def descriptor(self) -> ComponentDescriptor:
        """Return the configured component metadata."""
        return self._values.descriptor

    def supports(
        self,
        target: ModelTarget,
        task: TaskDescriptor,
        mode: InteractionMode,
    ) -> bool:
        """Record applicability and return the configured true result."""
        del target, task, mode
        self._recorder.record("supports")
        return True

    def prepare_plan(
        self,
        request: ModelRequest,
        access: ResolvedServiceAccess,
        mode: InteractionMode,
    ) -> ProtocolExecutionPlan:
        """Record planning and return the configured execution plan."""
        del request, access, mode
        self._recorder.record("prepare_plan")
        return self._values.execution_plan

    def build_request(
        self,
        request: ModelRequest,
        plan: ProtocolExecutionPlan,
    ) -> ProtocolRequestPlan:
        """Record request construction and retain the supplied plan identity."""
        del request
        self._recorder.record("build_request")
        assert plan is self._values.execution_plan
        return self._values.request_plan

    def parse_response(
        self,
        response: ErasedRuntimeValue,
    ) -> ParsedTaskResponse:
        """Record successful parsing and return service facts."""
        del response
        self._recorder.record("parse_response")
        return self._values.parsed_response

    def parse_error(
        self,
        error: ErasedRuntimeValue,
        metadata: TransportResponseMetadata,
    ) -> ModelInteractionError | None:
        """Record error parsing and return the configured normalized error."""
        del error, metadata
        self._recorder.record("parse_error")
        return self._values.parsed_error


class _MalformedAdapter(_RecordingAdapter):
    """Return one selected runtime value that violates the adapter contract."""

    __slots__ = ("_malformed_operation",)

    def __init__(
        self,
        values: _Values,
        malformed_operation: str,
    ) -> None:
        """Select the operation whose nominal result will be violated."""
        super().__init__(values, ComponentCallRecorder())
        self._malformed_operation = malformed_operation

    def supports(
        self,
        target: ModelTarget,
        task: TaskDescriptor,
        mode: InteractionMode,
    ) -> bool:
        """Return an integer only for the selected applicability violation."""
        if self._malformed_operation == "supports":
            return cast(bool, 1)
        return super().supports(target, task, mode)

    def prepare_plan(
        self,
        request: ModelRequest,
        access: ResolvedServiceAccess,
        mode: InteractionMode,
    ) -> ProtocolExecutionPlan:
        """Return an arbitrary object only for the planning violation."""
        if self._malformed_operation == "prepare_plan":
            return cast(ProtocolExecutionPlan, object())
        return super().prepare_plan(request, access, mode)

    def build_request(
        self,
        request: ModelRequest,
        plan: ProtocolExecutionPlan,
    ) -> ProtocolRequestPlan:
        """Return an arbitrary object only for the request-plan violation."""
        if self._malformed_operation == "build_request":
            return cast(ProtocolRequestPlan, object())
        if self._malformed_operation == "replace_plan":
            replacement = _values().execution_plan
            return ProtocolRequestPlan(self._values.request_plan.payload, replacement)
        return super().build_request(request, plan)

    def parse_response(
        self,
        response: ErasedRuntimeValue,
    ) -> ParsedTaskResponse:
        """Return an arbitrary object only for the success-parse violation."""
        if self._malformed_operation == "parse_response":
            return cast(ParsedTaskResponse, object())
        return super().parse_response(response)

    def parse_error(
        self,
        error: ErasedRuntimeValue,
        metadata: TransportResponseMetadata,
    ) -> ModelInteractionError | None:
        """Return an arbitrary object only for the error-parse violation."""
        if self._malformed_operation == "parse_error":
            return cast(ModelInteractionError, object())
        return super().parse_error(error, metadata)


class _AsyncAdapter:
    """Structurally complete adapter with one invalid asynchronous operation."""

    __slots__ = ("_delegate",)

    def __init__(self, delegate: _RecordingAdapter) -> None:
        """Retain a valid delegate for the four synchronous operations."""
        self._delegate = delegate

    @property
    def descriptor(self) -> ComponentDescriptor:
        """Return the valid delegate descriptor."""
        return self._delegate.descriptor

    async def supports(
        self,
        target: ModelTarget,
        task: TaskDescriptor,
        mode: InteractionMode,
    ) -> bool:
        """Return asynchronously in violation of the synchronous SPI."""
        return self._delegate.supports(target, task, mode)

    def prepare_plan(
        self,
        request: ModelRequest,
        access: ResolvedServiceAccess,
        mode: InteractionMode,
    ) -> ProtocolExecutionPlan:
        """Delegate planning without altering values."""
        return self._delegate.prepare_plan(request, access, mode)

    def build_request(
        self,
        request: ModelRequest,
        plan: ProtocolExecutionPlan,
    ) -> ProtocolRequestPlan:
        """Delegate request construction without altering values."""
        return self._delegate.build_request(request, plan)

    def parse_response(self, response: ErasedRuntimeValue) -> ParsedTaskResponse:
        """Delegate successful parsing without altering values."""
        return self._delegate.parse_response(response)

    def parse_error(
        self,
        error: ErasedRuntimeValue,
        metadata: TransportResponseMetadata,
    ) -> ModelInteractionError | None:
        """Delegate error parsing without altering values."""
        return self._delegate.parse_error(error, metadata)


def test_suite_accepts_stub_and_validates_all_adapter_results() -> None:
    """Reuse one suite across applicability, planning, build, and parse cases."""
    values = _values()
    suite = AdapterContractSuite(_stub(values))

    suite.assert_supports(
        cast(ModelTarget, object()),
        cast(TaskDescriptor, object()),
        cast(InteractionMode, object()),
        expected=True,
    )
    suite.assert_prepare_plan(
        cast(ModelRequest, object()),
        cast(ResolvedServiceAccess, object()),
        cast(InteractionMode, object()),
        assertion=_identity_assertion(values.execution_plan),
    )
    suite.assert_build_request(
        cast(ModelRequest, object()),
        values.execution_plan,
        assertion=_identity_assertion(values.request_plan),
    )
    suite.assert_parse_response(
        _successful_response(),
        assertion=_identity_assertion(values.parsed_response),
    )
    suite.assert_parse_error(
        _error_response(),
        _error_metadata(),
        assertion=_identity_assertion(values.parsed_error),
    )


def test_suite_accepts_custom_structural_adapter_and_preserves_call_order() -> None:
    """Require no SDK inheritance, registration, or framework-specific base."""
    values = _values()
    recorder = ComponentCallRecorder()
    adapter = _RecordingAdapter(values, recorder)
    accepted: TaskProtocolAdapter = adapter
    suite = AdapterContractSuite(accepted)

    suite.assert_supports(
        cast(ModelTarget, object()),
        cast(TaskDescriptor, object()),
        cast(InteractionMode, object()),
        expected=True,
    )
    suite.assert_prepare_plan(
        cast(ModelRequest, object()),
        cast(ResolvedServiceAccess, object()),
        cast(InteractionMode, object()),
        assertion=_identity_assertion(values.execution_plan),
    )
    suite.assert_build_request(
        cast(ModelRequest, object()),
        values.execution_plan,
        assertion=_identity_assertion(values.request_plan),
    )
    suite.assert_parse_response(
        _successful_response(),
        assertion=_identity_assertion(values.parsed_response),
    )
    suite.assert_parse_error(
        _error_response(),
        _error_metadata(),
        assertion=_identity_assertion(values.parsed_error),
    )

    assert recorder.calls == (
        "supports",
        "prepare_plan",
        "build_request",
        "parse_response",
        "parse_error",
    )


def test_suite_preserves_none_as_unrecognized_error_result() -> None:
    """Pass protocol-significant None to the caller assertion unchanged."""
    suite = AdapterContractSuite(_stub(_values(), parse_error_result=None))
    observed: list[ModelInteractionError | None] = []

    def assert_unrecognized(actual: ModelInteractionError | None) -> None:
        """Record and require the explicit unrecognized-error outcome."""
        assert actual is None
        observed.append(actual)

    suite.assert_parse_error(
        _error_response(),
        _error_metadata(),
        assertion=assert_unrecognized,
    )
    assert observed == [None]


def _unexpected_assertion(value: object) -> None:
    """Fail if a malformed adapter result reaches protocol-specific checks."""
    del value
    raise AssertionError("Protocol assertion must not receive an invalid result.")


def _exercise_malformed_result(
    suite: AdapterContractSuite,
    operation: str,
    values: _Values,
) -> None:
    """Invoke the selected suite assertion for a malformed adapter operation."""
    if operation == "supports":
        suite.assert_supports(
            cast(ModelTarget, object()),
            cast(TaskDescriptor, object()),
            cast(InteractionMode, object()),
            expected=True,
        )
        return
    if operation == "prepare_plan":
        suite.assert_prepare_plan(
            cast(ModelRequest, object()),
            cast(ResolvedServiceAccess, object()),
            cast(InteractionMode, object()),
            assertion=cast(
                Callable[[ProtocolExecutionPlan], None], _unexpected_assertion
            ),
        )
        return
    if operation in ("build_request", "replace_plan"):
        suite.assert_build_request(
            cast(ModelRequest, object()),
            values.execution_plan,
            assertion=cast(
                Callable[[ProtocolRequestPlan], None], _unexpected_assertion
            ),
        )
        return
    if operation == "parse_response":
        suite.assert_parse_response(
            _successful_response(),
            assertion=cast(Callable[[ParsedTaskResponse], None], _unexpected_assertion),
        )
        return
    suite.assert_parse_error(
        _error_response(),
        _error_metadata(),
        assertion=cast(
            Callable[[ModelInteractionError | None], None], _unexpected_assertion
        ),
    )


def test_suite_rejects_every_malformed_result_before_caller_assertion() -> None:
    """Enforce nominal outputs and prepared-plan identity at runtime."""
    values = _values()
    cases = (
        ("supports", "supports must return a bool"),
        ("prepare_plan", "prepare_plan must return a ProtocolExecutionPlan"),
        ("build_request", "build_request must return a ProtocolRequestPlan"),
        ("replace_plan", "must retain the prepared plan instance"),
        ("parse_response", "parse_response must return a ParsedTaskResponse"),
        ("parse_error", "parse_error must return a ModelInteractionError or None"),
    )

    for operation, message in cases:
        suite = AdapterContractSuite(_MalformedAdapter(values, operation))
        try:
            _exercise_malformed_result(suite, operation, values)
        except AssertionError as error:
            assert message in str(error)
        else:
            raise AssertionError("Expected a malformed adapter result to fail.")


def test_suite_propagates_adapter_and_assertion_failures_by_identity() -> None:
    """Avoid wrapping failures owned by adapters or contract-case assertions."""
    values = _values()
    adapter_failure = RuntimeError("adapter failed")
    suite = AdapterContractSuite(_stub(values, supports_error=adapter_failure))

    try:
        suite.assert_supports(
            cast(ModelTarget, object()),
            cast(TaskDescriptor, object()),
            cast(InteractionMode, object()),
            expected=True,
        )
    except RuntimeError as error:
        assert error is adapter_failure
    else:
        raise AssertionError("Expected the adapter failure to propagate.")

    assertion_failure = LookupError("fixture comparison failed")

    def failing_assertion(actual: ProtocolExecutionPlan) -> None:
        """Raise the exact caller-owned fixture assertion failure."""
        assert actual is values.execution_plan
        raise assertion_failure

    conforming_suite = AdapterContractSuite(_stub(values))
    try:
        conforming_suite.assert_prepare_plan(
            cast(ModelRequest, object()),
            cast(ResolvedServiceAccess, object()),
            cast(InteractionMode, object()),
            assertion=failing_assertion,
        )
    except LookupError as error:
        assert error is assertion_failure
    else:
        raise AssertionError("Expected the assertion failure to propagate.")


def test_suite_rejects_invalid_adapter_and_assertion_setup_before_calls() -> None:
    """Fail fast on structural, descriptor, synchronization, and callback misuse."""
    values = _values()
    recorder = ComponentCallRecorder()
    valid_adapter = _RecordingAdapter(values, recorder)

    invalid_adapter_calls: tuple[tuple[Callable[[], object], str], ...] = (
        (
            lambda: AdapterContractSuite(cast(TaskProtocolAdapter, object())),
            "must implement TaskProtocolAdapter",
        ),
        (
            lambda: AdapterContractSuite(
                _RecordingAdapter(
                    _Values(
                        cast(ComponentDescriptor, object()),
                        values.execution_plan,
                        values.request_plan,
                        values.parsed_response,
                        values.parsed_error,
                    ),
                    ComponentCallRecorder(),
                )
            ),
            "descriptor must be a ComponentDescriptor",
        ),
        (
            lambda: AdapterContractSuite(
                cast(
                    TaskProtocolAdapter,
                    _AsyncAdapter(valid_adapter),
                )
            ),
            "operations must be synchronous",
        ),
    )
    for action, message in invalid_adapter_calls:
        try:
            action()
        except TypeError as error:
            assert message in str(error)
        else:
            raise AssertionError("Expected invalid adapter setup to fail.")

    suite = AdapterContractSuite(valid_adapter)

    async def asynchronous_assertion(actual: ProtocolExecutionPlan) -> None:
        """Represent a callback that the synchronous suite must reject."""
        del actual

    invalid_assertions: tuple[Callable[[ProtocolExecutionPlan], None], ...] = (
        cast(Callable[[ProtocolExecutionPlan], None], object()),
        cast(Callable[[ProtocolExecutionPlan], None], asynchronous_assertion),
    )
    for assertion in invalid_assertions:
        try:
            suite.assert_prepare_plan(
                cast(ModelRequest, object()),
                cast(ResolvedServiceAccess, object()),
                cast(InteractionMode, object()),
                assertion=assertion,
            )
        except TypeError:
            pass
        else:
            raise AssertionError("Expected invalid assertion setup to fail.")
    assert recorder.calls == ()

    try:
        suite.assert_supports(
            cast(ModelTarget, object()),
            cast(TaskDescriptor, object()),
            cast(InteractionMode, object()),
            expected=cast(bool, 1),
        )
    except TypeError as error:
        assert "expected must be a bool" in str(error)
    else:
        raise AssertionError("Expected invalid supports expectation to fail.")
    assert recorder.calls == ()


def test_suite_exposes_only_independent_adapter_contract_assertions() -> None:
    """Keep fixtures, protocol comparison, I/O, and pipeline ownership external."""
    suite = AdapterContractSuite(_stub(_values()))

    assert tuple(inspect.signature(AdapterContractSuite).parameters) == ("adapter",)
    for method_name in (
        "assert_supports",
        "assert_prepare_plan",
        "assert_build_request",
        "assert_parse_response",
        "assert_parse_error",
    ):
        method = getattr(AdapterContractSuite, method_name)
        assert not inspect.iscoroutinefunction(method)
    assert not hasattr(suite, "__dict__")

    # Fixture ownership and adjacent runtime stages remain explicit in the
    # calling test instead of being hidden behind one monolithic run operation.
    for forbidden_member in (
        "run",
        "load_fixture",
        "compare_fixture",
        "encode",
        "authorize",
        "send",
        "decode",
        "assemble_output",
        "reset",
    ):
        assert not hasattr(suite, forbidden_member)
