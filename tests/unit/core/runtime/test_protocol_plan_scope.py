"""Tests for the R1 unary JSON HTTP bytes execution-plan gate."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from mconet.core.domain import (
    Headers,
    MediaType,
    ModelInteractionError,
    OpenIdentifier,
    QueryParameters,
    UriValue,
)
from mconet.core.runtime._protocol_plan_scope import (
    validate_r1_protocol_execution_plan,
)
from mconet.core.spi import (
    BodySigningRequirement,
    ComponentRole,
    ComponentTypeContract,
    ComponentTypePort,
    DecoderSelection,
    EncoderSelection,
    PlannedComponentSelection,
    ProtocolExecutionPlan,
    TransportRequestPlan,
    TransportSelection,
)


def _capture(action: Callable[[], object]) -> BaseException:
    """Run one action and return the exception it raises."""
    try:
        action()
    except BaseException as error:
        return error
    raise AssertionError("Expected the action to fail.")


@dataclass(frozen=True, slots=True)
class _Mode:
    """Structural interaction mode."""

    id: OpenIdentifier


@dataclass(frozen=True, slots=True)
class _Authorization:
    """Opaque authorization with no credential payload."""

    kind: OpenIdentifier


def _plan(
    *,
    media_type: MediaType | None = None,
    transport_kind: OpenIdentifier | None = None,
    capabilities: frozenset[OpenIdentifier] | None = None,
    mode_components: tuple[PlannedComponentSelection, ...] = (),
    type_contract: ComponentTypeContract | None = None,
) -> ProtocolExecutionPlan:
    """Build one execution plan with the requested scope dimensions."""
    # None selects the R1 default. Callers that need another value pass it.
    resolved_media = (
        MediaType("application", "json") if media_type is None else media_type
    )
    resolved_transport = (
        OpenIdentifier("http") if transport_kind is None else transport_kind
    )
    resolved_capabilities: frozenset[OpenIdentifier] = (
        frozenset() if capabilities is None else capabilities
    )
    contract = type_contract
    if contract is None:
        json_type = OpenIdentifier("json.value")
        json_media = MediaType("application", "json")
        contract = ComponentTypeContract(
            inputs=(ComponentTypePort("response", json_type, None, json_media),),
            outputs=(ComponentTypePort("payload", json_type, None, json_media),),
        )
    return ProtocolExecutionPlan(
        transport_plan=TransportRequestPlan(
            endpoint=UriValue("https://models.example.test", True),
            path="/v1/chat/completions",
            method="POST",
            headers=Headers(),
            query=QueryParameters(),
            authorization=_Authorization(OpenIdentifier("authorization.none")),
            body_signing_requirement=BodySigningRequirement(),
        ),
        payload_encoder=EncoderSelection(resolved_media),
        success_decoder=DecoderSelection(resolved_media),
        error_decoder=DecoderSelection(resolved_media),
        transport=TransportSelection(resolved_transport, resolved_capabilities),
        mode_components=mode_components,
        type_contract=contract,
    )


def test_unary_json_http_plan_is_accepted() -> None:
    """Verify the frozen R1 plan shape is returned unchanged."""
    plan = _plan()

    assert (
        validate_r1_protocol_execution_plan(_Mode(OpenIdentifier("unary")), plan)
        is plan
    )


def test_transport_bytes_ports_are_inside_the_r1_scope() -> None:
    """Verify a bytes transport boundary is also an R1 plan."""
    bytes_type = OpenIdentifier("transport.bytes")
    plan = _plan(
        type_contract=ComponentTypeContract(
            inputs=(ComponentTypePort("body", bytes_type),),
            outputs=(ComponentTypePort("response", bytes_type),),
        )
    )

    assert (
        validate_r1_protocol_execution_plan(_Mode(OpenIdentifier("unary")), plan)
        is plan
    )


def test_non_unary_mode_fails_before_later_resolution() -> None:
    """Verify a streaming mode is rejected and the plan is not replaced."""
    plan = _plan()
    calls: list[str] = []

    def _resolve() -> None:
        validate_r1_protocol_execution_plan(
            _Mode(OpenIdentifier("server_stream")),
            plan,
        )
        calls.append("resolved")

    error = _capture(_resolve)

    assert isinstance(error, ModelInteractionError)
    assert error.code == "unsupported_interaction_mode"
    assert error.phase.id.value == "protocol_planning"
    assert calls == []


def test_mode_components_fail_as_non_unary() -> None:
    """Verify streaming component requirements are outside the unary scope."""
    plan = _plan(
        mode_components=(
            PlannedComponentSelection(
                ComponentRole(OpenIdentifier("stream.framer")),
                True,
            ),
        )
    )

    error = _capture(
        lambda: validate_r1_protocol_execution_plan(
            _Mode(OpenIdentifier("unary")), plan
        )
    )

    assert isinstance(error, ModelInteractionError)
    assert error.code == "unsupported_interaction_mode"


def test_non_json_non_http_and_non_bytes_plans_fail() -> None:
    """Verify each non-R1 plan dimension fails with the plan scope code."""
    protobuf = _plan(media_type=MediaType("application", "protobuf"))
    grpc = _plan(transport_kind=OpenIdentifier("grpc"))
    foreign = _plan(
        type_contract=ComponentTypeContract(
            outputs=(ComponentTypePort("payload", OpenIdentifier("grpc.message")),)
        )
    )

    for plan in (protobuf, grpc, foreign):
        error = _capture(
            lambda plan=plan: validate_r1_protocol_execution_plan(
                _Mode(OpenIdentifier("unary")),
                plan,
            )
        )
        assert isinstance(error, ModelInteractionError)
        assert error.code == "unsupported_protocol_plan"
        assert error.phase.id.value == "protocol_planning"
