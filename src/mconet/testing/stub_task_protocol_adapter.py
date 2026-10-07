"""Configurable test double for the complete task protocol adapter contract."""

from __future__ import annotations

from typing import cast

from mconet.core.domain import (
    InteractionMode,
    ModelInteractionError,
    ModelRequest,
    ModelTarget,
    ParsedTaskResponse,
    ResolvedServiceAccess,
    TaskDescriptor,
)
from mconet.core.spi import (
    ComponentDescriptor,
    ErasedRuntimeValue,
    ProtocolExecutionPlan,
    ProtocolRequestPlan,
    TransportResponseMetadata,
)


class StubTaskProtocolAdapter:
    """Return or raise independently configured outcomes for every adapter step.

    The stub structurally implements ``TaskProtocolAdapter`` without SDK
    inheritance. Construction requires one valid return value for each method;
    an optional method-specific exception overrides that value when invoked.
    ``parse_error_result`` may be ``None`` to model an unrecognized service
    error independently from a configured thrown failure.

    Results and failures are retained by identity and never copied, normalized,
    wrapped, or translated. Methods ignore their inputs after crossing the
    statically typed protocol boundary and perform no planning, payload mapping,
    output assembly, authorization, transport, monitoring, or other I/O.

    This test double deliberately records no calls and offers no mutable
    reconfiguration API. Ordered invocation evidence belongs to the separate
    component call recorder, while each test receives deterministic behavior
    from its fixed construction-time configuration.
    """

    __slots__ = (
        "_build_request_error",
        "_build_request_result",
        "_descriptor",
        "_parse_error_error",
        "_parse_error_result",
        "_parse_response_error",
        "_parse_response_result",
        "_prepare_plan_error",
        "_prepare_plan_result",
        "_supports_error",
        "_supports_result",
    )

    def __init__(
        self,
        descriptor: ComponentDescriptor,
        *,
        supports_result: bool,
        prepare_plan_result: ProtocolExecutionPlan,
        build_request_result: ProtocolRequestPlan,
        parse_response_result: ParsedTaskResponse,
        parse_error_result: ModelInteractionError | None,
        supports_error: BaseException | None = None,
        prepare_plan_error: BaseException | None = None,
        build_request_error: BaseException | None = None,
        parse_response_error: BaseException | None = None,
        parse_error_error: BaseException | None = None,
    ) -> None:
        """Validate and retain one deterministic outcome per adapter method.

        Args:
            descriptor: Static metadata exposed through ``RuntimeComponent``.
            supports_result: Boolean returned by :meth:`supports`.
            prepare_plan_result: Exact plan returned by :meth:`prepare_plan`.
            build_request_result: Exact request plan returned by
                :meth:`build_request`.
            parse_response_result: Exact successful parse result returned by
                :meth:`parse_response`.
            parse_error_result: Exact normalized error or ``None`` returned by
                :meth:`parse_error`.
            supports_error: Optional exact exception raised by :meth:`supports`.
            prepare_plan_error: Optional exact exception raised by
                :meth:`prepare_plan`.
            build_request_error: Optional exact exception raised by
                :meth:`build_request`.
            parse_response_error: Optional exact exception raised by
                :meth:`parse_response`.
            parse_error_error: Optional exact exception raised by
                :meth:`parse_error`.

        Raises:
            TypeError: If metadata, a configured result, or a configured failure
                does not satisfy its nominal contract.
        """
        descriptor_value = cast(object, descriptor)
        supports_value = cast(object, supports_result)
        prepare_plan_value = cast(object, prepare_plan_result)
        build_request_value = cast(object, build_request_result)
        parse_response_value = cast(object, parse_response_result)
        parse_error_value = cast(object, parse_error_result)

        # Validate every configured result eagerly. A test setup error must fail
        # at construction rather than appearing as an unrelated runtime branch.
        if not isinstance(descriptor_value, ComponentDescriptor):
            raise TypeError("descriptor must be a ComponentDescriptor.")
        if type(supports_value) is not bool:
            raise TypeError("supports_result must be a bool.")
        if not isinstance(prepare_plan_value, ProtocolExecutionPlan):
            raise TypeError("prepare_plan_result must be a ProtocolExecutionPlan.")
        if not isinstance(build_request_value, ProtocolRequestPlan):
            raise TypeError("build_request_result must be a ProtocolRequestPlan.")
        if not isinstance(parse_response_value, ParsedTaskResponse):
            raise TypeError("parse_response_result must be a ParsedTaskResponse.")
        if parse_error_value is not None and not isinstance(
            parse_error_value, ModelInteractionError
        ):
            raise TypeError(
                "parse_error_result must be a ModelInteractionError or None."
            )

        failures = (
            ("supports_error", supports_error),
            ("prepare_plan_error", prepare_plan_error),
            ("build_request_error", build_request_error),
            ("parse_response_error", parse_response_error),
            ("parse_error_error", parse_error_error),
        )
        for name, failure in failures:
            # BaseException intentionally includes cancellation and other control
            # failures needed by deterministic fault-injection tests.
            failure_value = cast(object, failure)
            if failure_value is not None and not isinstance(
                failure_value, BaseException
            ):
                raise TypeError(f"{name} must be a BaseException or None.")

        self._descriptor = descriptor
        self._supports_result = supports_result
        self._prepare_plan_result = prepare_plan_result
        self._build_request_result = build_request_result
        self._parse_response_result = parse_response_result
        self._parse_error_result = parse_error_result
        self._supports_error = supports_error
        self._prepare_plan_error = prepare_plan_error
        self._build_request_error = build_request_error
        self._parse_response_error = parse_response_error
        self._parse_error_error = parse_error_error

    @property
    def descriptor(self) -> ComponentDescriptor:
        """Return the exact immutable component metadata supplied at construction."""
        # A read-only property satisfies RuntimeComponent without letting tests
        # replace metadata after selection or plan construction.
        return self._descriptor

    def supports(
        self,
        target: ModelTarget,
        task: TaskDescriptor,
        mode: InteractionMode,
    ) -> bool:
        """Return configured applicability or raise its configured failure."""
        # Inputs cross the complete protocol signature but are deliberately not
        # inspected; this stub models a predetermined selection branch only.
        del target, task, mode
        _raise_configured(self._supports_error)
        return self._supports_result

    def prepare_plan(
        self,
        request: ModelRequest,
        access: ResolvedServiceAccess,
        mode: InteractionMode,
    ) -> ProtocolExecutionPlan:
        """Return the configured execution plan or raise its configured failure."""
        # No credential, artifact, component, or network behavior is performed;
        # the exact prebuilt plan is the complete configured outcome.
        del request, access, mode
        _raise_configured(self._prepare_plan_error)
        return self._prepare_plan_result

    def build_request(
        self,
        request: ModelRequest,
        plan: ProtocolExecutionPlan,
    ) -> ProtocolRequestPlan:
        """Return the configured request plan or raise its configured failure."""
        # Request mapping, payload creation, and plan consistency are owned by
        # the configured result's producer, not recomputed by this test double.
        del request, plan
        _raise_configured(self._build_request_error)
        return self._build_request_result

    def parse_response(
        self,
        response: ErasedRuntimeValue,
    ) -> ParsedTaskResponse:
        """Return the configured parsed response or raise its configured failure."""
        # The decoded native value remains untouched so the stub cannot perform
        # hidden type retrieval, response mapping, or ModelOutput assembly.
        del response
        _raise_configured(self._parse_response_error)
        return self._parse_response_result

    def parse_error(
        self,
        error: ErasedRuntimeValue,
        metadata: TransportResponseMetadata,
    ) -> ModelInteractionError | None:
        """Return the configured error mapping or raise its configured failure."""
        # None remains a real configured return value meaning unrecognized; the
        # separate failure slot prevents ambiguity with a thrown exception.
        del error, metadata
        _raise_configured(self._parse_error_error)
        return self._parse_error_result


def _raise_configured(failure: BaseException | None) -> None:
    """Raise one exact configured failure or return without side effects."""
    if failure is not None:
        # Preserve identity, type, message, custom fields, and control-flow class
        # so tests observe precisely the failure they configured.
        raise failure
