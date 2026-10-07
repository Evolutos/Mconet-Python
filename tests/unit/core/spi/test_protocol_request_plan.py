"""Composition and boundary tests for immutable protocol request plans."""

from collections.abc import Callable
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
    DecoderSelection,
    EncoderSelection,
    ErasedRuntimeValue,
    ProtocolExecutionPlan,
    ProtocolRequestPlan,
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
        # Match request-plan wording so a fixture failure cannot accidentally
        # satisfy a negative composition test for an unrelated boundary.
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


@dataclass(frozen=True, slots=True)
class _Authorization:
    """Application authorization satisfying the open structural boundary."""

    kind: OpenIdentifier
    """Open discriminator retained for later authorization-handler selection."""


def _execution_plan() -> ProtocolExecutionPlan:
    """Build a complete execution plan for request-plan composition tests."""
    # Keep each plan facet explicit so the request wrapper test proves the whole
    # execution plan is retained rather than only its nested transport request.
    transport_plan = TransportRequestPlan(
        endpoint=UriValue("https://models.example.test", True),
        path="/v1/chat/completions",
        method="POST",
        headers=Headers(),
        query=QueryParameters(),
        authorization=_Authorization(OpenIdentifier("authorization.bearer")),
        body_signing_requirement=BodySigningRequirement(),
    )
    json_media_type = MediaType("application", "json")
    return ProtocolExecutionPlan(
        transport_plan=transport_plan,
        payload_encoder=EncoderSelection(json_media_type, "openai.chat.request"),
        success_decoder=DecoderSelection(
            json_media_type,
            "openai.chat.response",
        ),
        error_decoder=DecoderSelection(json_media_type, "openai.error"),
        transport=TransportSelection(OpenIdentifier("http")),
    )


def test_protocol_request_plan_preserves_payload_and_execution_plan_identity() -> None:
    """Verify the adapter output retains both completed values without copying."""
    native_payload = {"messages": [{"role": "user", "content": "hello"}]}
    payload = ErasedRuntimeValue(
        OpenIdentifier("openai.chat.request"),
        native_payload,
        "openai.chat.request",
    )
    execution_plan = _execution_plan()

    request_plan = ProtocolRequestPlan(payload, execution_plan)

    # Identity preservation keeps the native object and every fixed execution
    # criterion aligned with the exact adapter invocation that produced them.
    assert request_plan.payload is payload
    assert request_plan.payload.value is native_payload
    assert request_plan.execution_plan is execution_plan
    assert request_plan.execution_plan.transport_plan is execution_plan.transport_plan


def test_protocol_request_plan_keeps_payload_unencoded() -> None:
    """Verify construction does not serialize or reinterpret the native payload."""
    native_payload = object()
    payload = ErasedRuntimeValue(
        OpenIdentifier("protocol.vendor.request"), native_payload
    )

    request_plan = ProtocolRequestPlan(payload, _execution_plan())

    # Encoding belongs to the selected PayloadEncoder after component and type
    # checks; the request plan therefore exposes the same erased native object.
    assert request_plan.payload.value is native_payload
    assert request_plan.payload.type_id == OpenIdentifier("protocol.vendor.request")
    assert not hasattr(request_plan, "body")
    assert not hasattr(request_plan, "transport_request")


def test_protocol_request_plan_has_frozen_exact_field_surface() -> None:
    """Verify only the payload and governing execution plan form this value."""
    request_plan = ProtocolRequestPlan(
        ErasedRuntimeValue(OpenIdentifier("protocol.request"), object()),
        _execution_plan(),
    )

    # The nested execution plan is the sole owner of request, codec, transport,
    # mode, and type facts, preventing duplicate fields from drifting apart.
    assert tuple(field.name for field in fields(ProtocolRequestPlan)) == (
        "payload",
        "execution_plan",
    )
    assert not hasattr(request_plan, "transport_plan")
    assert not hasattr(request_plan, "encoder")
    assert not hasattr(request_plan, "decoder")
    _assert_raises(
        FrozenInstanceError,
        lambda: request_plan.__setattr__("payload", request_plan.payload),
        "cannot assign to field",
    )


def test_protocol_request_plan_requires_erased_payload() -> None:
    """Verify a raw native payload cannot bypass portable type metadata."""
    # Even JSON-compatible data must be wrapped because encoder selection and
    # component compatibility depend on type and optional schema identifiers.
    _assert_raises(
        TypeError,
        lambda: ProtocolRequestPlan(
            cast(ErasedRuntimeValue, {"message": "raw"}),
            _execution_plan(),
        ),
        "payload must be an ErasedRuntimeValue",
    )


def test_protocol_request_plan_requires_complete_execution_plan() -> None:
    """Verify a transport-only plan cannot replace complete execution criteria."""
    execution_plan = _execution_plan()
    payload = ErasedRuntimeValue(OpenIdentifier("protocol.request"), object())

    # A TransportRequestPlan lacks encoder, separate decoders, transport kind,
    # mode components, and type contract, so accepting it would lose fixed facts.
    _assert_raises(
        TypeError,
        lambda: ProtocolRequestPlan(
            payload,
            cast(ProtocolExecutionPlan, execution_plan.transport_plan),
        ),
        "execution_plan must be a ProtocolExecutionPlan",
    )
