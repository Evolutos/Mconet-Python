"""Composition and boundary tests for immutable protocol execution plans."""

from collections.abc import Callable, Mapping
from dataclasses import FrozenInstanceError, dataclass, fields
from typing import cast

from mconet.core.domain import (
    Headers,
    MediaType,
    OpenIdentifier,
    QueryParameters,
    UriValue,
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


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    try:
        action()
    except exception_type as error:
        # Match plan-owned wording so a nested fixture failure cannot make an
        # invalid composition test pass for an unrelated reason.
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


@dataclass(frozen=True, slots=True)
class _Authorization:
    """Application authorization satisfying the open structural boundary."""

    kind: OpenIdentifier
    """Open discriminator consumed by a later authorization resolver."""


def _transport_plan() -> TransportRequestPlan:
    """Build complete protocol-owned HTTP request facts for plan tests."""
    # Use the no-signing requirement expected by the initial HTTP path while
    # retaining the same open authorization boundary used by custom handlers.
    return TransportRequestPlan(
        endpoint=UriValue("https://models.example.test", True),
        path="/v1/chat/completions",
        method="POST",
        headers=Headers(),
        query=QueryParameters(),
        authorization=_Authorization(OpenIdentifier("authorization.bearer")),
        body_signing_requirement=BodySigningRequirement(),
    )


def _plan(
    *,
    mode_components: tuple[PlannedComponentSelection, ...] = (),
    extensions: Mapping[str, object] | None = None,
) -> ProtocolExecutionPlan:
    """Build a complete unary JSON, HTTP, and bytes execution plan."""
    # The representative contract names bytes explicitly so the plan exposes all
    # facts needed by the later release-scope and component-compatibility gates.
    bytes_type = OpenIdentifier("transport.bytes")
    contract = ComponentTypeContract(
        inputs=(ComponentTypePort("payload", bytes_type),),
        outputs=(ComponentTypePort("response", bytes_type),),
    )
    extension_values: Mapping[str, object] = {} if extensions is None else extensions
    return ProtocolExecutionPlan(
        transport_plan=_transport_plan(),
        payload_encoder=EncoderSelection(MediaType("application", "json")),
        success_decoder=DecoderSelection(MediaType("application", "json")),
        error_decoder=DecoderSelection(
            MediaType("application", "json"),
            "openai.error",
        ),
        transport=TransportSelection(OpenIdentifier("http")),
        mode_components=mode_components,
        type_contract=contract,
        extensions=extension_values,
    )


def test_protocol_execution_plan_preserves_initial_execution_constraints() -> None:
    """Verify unary JSON, HTTP, and bytes facts remain independently observable."""
    plan = _plan()

    # Unary requires no additional streaming or operation components. Encoding
    # and both response paths state JSON independently rather than sharing one
    # decoder selection, while transport and byte ports remain explicit.
    assert plan.mode_components == ()
    assert plan.payload_encoder.media_type == MediaType("application", "json")
    assert plan.success_decoder.media_type == MediaType("application", "json")
    assert plan.error_decoder.media_type == MediaType("application", "json")
    assert plan.error_decoder.schema_id == "openai.error"
    assert plan.transport.transport_kind == OpenIdentifier("http")
    assert plan.type_contract.inputs[0].type_id == OpenIdentifier("transport.bytes")
    assert plan.type_contract.outputs[0].type_id == OpenIdentifier("transport.bytes")


def test_protocol_execution_plan_preserves_separate_mode_requirements() -> None:
    """Verify ordered mode roles remain declarative and immutable."""
    framer = PlannedComponentSelection(
        ComponentRole(OpenIdentifier("stream.framer")),
        True,
        frozenset({OpenIdentifier("stream.sse")}),
    )
    mapper = PlannedComponentSelection(
        ComponentRole(OpenIdentifier("stream.event-mapper")),
        False,
    )

    plan = _plan(mode_components=(framer, mapper))

    # Non-unary requirements must survive plan creation so the dedicated runtime
    # scope gate can reject them before I/O in the initial release and future
    # runtimes can resolve them without changing this open plan representation.
    assert plan.mode_components == (framer, mapper)
    assert plan.mode_components[0] is framer
    assert plan.mode_components[1] is mapper


def test_protocol_execution_plan_snapshots_extension_membership() -> None:
    """Verify caller mapping changes cannot alter a completed execution plan."""
    marker: list[str] = ["opaque"]
    source: dict[str, object] = {"dialect": "vendor", "marker": marker}

    plan = _plan(extensions=source)
    source["dialect"] = "changed"
    source["later"] = True

    # Top-level membership is detached and read-only, while opaque extension
    # values remain by identity for the protocol adapter that owns their meaning.
    assert plan.extensions == {"dialect": "vendor", "marker": marker}
    assert plan.extensions["marker"] is marker
    assert "later" not in plan.extensions
    assert not hasattr(plan.extensions, "__setitem__")


def test_protocol_execution_plan_defaults_to_shared_empty_extensions() -> None:
    """Verify omitted extension mappings are safely immutable and allocation-free."""
    first = _plan()
    second = _plan()

    # Empty membership contains no nested state, so sharing the read-only mapping
    # cannot couple otherwise independent interaction plans.
    assert first.extensions == {}
    assert first.extensions is second.extensions
    assert not hasattr(first.extensions, "__setitem__")


def test_protocol_execution_plan_has_frozen_current_field_surface() -> None:
    """Verify the plan contains only currently implemented execution facts."""
    plan = _plan()

    # Resolved components, payload bytes, responses, and future capability or
    # artifact resolution values belong to their own work packages and stages.
    assert tuple(field.name for field in fields(ProtocolExecutionPlan)) == (
        "transport_plan",
        "payload_encoder",
        "success_decoder",
        "error_decoder",
        "transport",
        "mode_components",
        "type_contract",
        "extensions",
    )
    assert not hasattr(plan, "components")
    assert not hasattr(plan, "payload")
    assert not hasattr(plan, "response")
    assert not hasattr(plan, "artifact_resolution_plan")
    assert not hasattr(plan, "capability_requirements")
    _assert_raises(
        FrozenInstanceError,
        lambda: plan.__setattr__("mode_components", ()),
        "cannot assign to field",
    )


def test_protocol_execution_plan_requires_nominal_plan_values() -> None:
    """Verify raw dynamic values cannot bypass completed planning boundaries."""
    plan = _plan()
    cases: tuple[tuple[str, Callable[[], object]], ...] = (
        (
            "transport_plan must be a TransportRequestPlan",
            lambda: ProtocolExecutionPlan(
                cast(TransportRequestPlan, object()),
                plan.payload_encoder,
                plan.success_decoder,
                plan.error_decoder,
                plan.transport,
            ),
        ),
        (
            "payload_encoder must be an EncoderSelection",
            lambda: ProtocolExecutionPlan(
                plan.transport_plan,
                cast(EncoderSelection, object()),
                plan.success_decoder,
                plan.error_decoder,
                plan.transport,
            ),
        ),
        (
            "success_decoder must be a DecoderSelection",
            lambda: ProtocolExecutionPlan(
                plan.transport_plan,
                plan.payload_encoder,
                cast(DecoderSelection, object()),
                plan.error_decoder,
                plan.transport,
            ),
        ),
        (
            "error_decoder must be a DecoderSelection",
            lambda: ProtocolExecutionPlan(
                plan.transport_plan,
                plan.payload_encoder,
                plan.success_decoder,
                cast(DecoderSelection, object()),
                plan.transport,
            ),
        ),
        (
            "transport must be a TransportSelection",
            lambda: ProtocolExecutionPlan(
                plan.transport_plan,
                plan.payload_encoder,
                plan.success_decoder,
                plan.error_decoder,
                cast(TransportSelection, object()),
            ),
        ),
    )

    # Exercise every nominal composition boundary independently so error messages
    # identify the exact malformed input instead of leaking attribute failures.
    for message, action in cases:
        _assert_raises(TypeError, action, message)


def test_protocol_execution_plan_requires_immutable_mode_components() -> None:
    """Verify mode requirements use tuple storage and valid selection values."""
    plan = _plan()

    # A list could change after planning, while an arbitrary tuple member would
    # bypass the role, presence, and capability invariants of its value object.
    _assert_raises(
        TypeError,
        lambda: ProtocolExecutionPlan(
            plan.transport_plan,
            plan.payload_encoder,
            plan.success_decoder,
            plan.error_decoder,
            plan.transport,
            cast(tuple[PlannedComponentSelection, ...], []),
        ),
        "mode_components must be a tuple",
    )
    _assert_raises(
        TypeError,
        lambda: ProtocolExecutionPlan(
            plan.transport_plan,
            plan.payload_encoder,
            plan.success_decoder,
            plan.error_decoder,
            plan.transport,
            cast(tuple[PlannedComponentSelection, ...], (object(),)),
        ),
        "mode_components must contain PlannedComponentSelection values",
    )


def test_protocol_execution_plan_requires_contract_and_extension_mapping() -> None:
    """Verify runtime ports and protocol extensions retain stable shapes."""
    plan = _plan()

    # Raw port data cannot replace the declared contract, and extensions must be
    # a named string-key mapping so later consumers have deterministic lookup.
    _assert_raises(
        TypeError,
        lambda: ProtocolExecutionPlan(
            plan.transport_plan,
            plan.payload_encoder,
            plan.success_decoder,
            plan.error_decoder,
            plan.transport,
            type_contract=cast(ComponentTypeContract, ()),
        ),
        "type_contract must be a ComponentTypeContract",
    )
    _assert_raises(
        TypeError,
        lambda: ProtocolExecutionPlan(
            plan.transport_plan,
            plan.payload_encoder,
            plan.success_decoder,
            plan.error_decoder,
            plan.transport,
            extensions=cast(Mapping[str, object], ()),
        ),
        "extensions must be a mapping",
    )
    _assert_raises(
        TypeError,
        lambda: ProtocolExecutionPlan(
            plan.transport_plan,
            plan.payload_encoder,
            plan.success_decoder,
            plan.error_decoder,
            plan.transport,
            extensions=cast(Mapping[str, object], {1: "invalid"}),
        ),
        "extensions keys must be strings",
    )
