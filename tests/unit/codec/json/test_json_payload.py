"""Port-alignment tests for the frozen R1 JSON payload contract."""

from collections.abc import Callable
from dataclasses import FrozenInstanceError, dataclass, fields
from typing import cast

from mconet.codec.json import JsonPayload
from mconet.core.domain import (
    Headers,
    JsonValue,
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
) -> BaseException:
    """Return the expected exception after checking its stable message fragment."""
    try:
        action()
    except exception_type as error:
        # Stable fragments distinguish the JSON port failure from an unrelated
        # fixture or Python runtime error.
        assert message in str(error)
        return error
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


@dataclass(frozen=True, slots=True)
class _Authorization:
    """Structural authorization value required by a transport request plan."""

    kind: OpenIdentifier
    """Open discriminator retained only to satisfy the plan boundary."""


class _NativePayload:
    """Non-JSON object that remains valid inside a widened erased port."""


def _execution_plan() -> ProtocolExecutionPlan:
    """Build the minimum execution plan that can carry an adapter payload."""
    # The plan exists only to prove the JSON envelope satisfies the adapter
    # payload port. It does not select or invoke a codec.
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
        success_decoder=DecoderSelection(json_media_type, "openai.chat.response"),
        error_decoder=DecoderSelection(json_media_type, "openai.error"),
        transport=TransportSelection(OpenIdentifier("http")),
    )


def test_json_payload_preserves_every_json_category_and_port_identity() -> None:
    """Verify primitives, arrays, and objects stay on the erased port."""
    array_value: list[JsonValue] = ["hello", 42, False, None]
    object_value: dict[str, JsonValue] = {
        "text": "café😀𠀋",
        "nested": {"enabled": True},
        "items": [1, 2, 3],
    }
    type_ids = [
        OpenIdentifier("json.null"),
        OpenIdentifier("json.boolean"),
        OpenIdentifier("json.number"),
        OpenIdentifier("json.string"),
        OpenIdentifier("json.array"),
        OpenIdentifier("json.object"),
    ]
    values: tuple[JsonValue, ...] = (
        None,
        True,
        42,
        "",
        array_value,
        object_value,
    )

    payloads = [
        JsonPayload(type_id, value)
        for type_id, value in zip(type_ids, values, strict=True)
    ]
    object_payload = JsonPayload(
        type_ids[-1],
        object_value,
        "schema://json.contract/object/1",
    )

    # Each category keeps the producer type id and the exact JSON object. An
    # omitted schema stays None, while an explicit schema string is preserved.
    assert [payload.type_id for payload in payloads] == type_ids
    assert [payload.value for payload in payloads] == list(values)
    assert payloads[4].value is array_value
    assert all(payload.schema_id is None for payload in payloads)
    assert object_payload.schema_id == "schema://json.contract/object/1"
    assert object_payload.value is object_value
    assert JsonPayload(type_ids[3], "kept", "").schema_id == ""
    assert JsonPayload(OpenIdentifier("json.array"), []).value == []
    assert JsonPayload(OpenIdentifier("json.object"), {}).value == {}


def test_json_payload_aligns_with_the_erased_adapter_port() -> None:
    """Verify a JSON payload can occupy the adapter payload port unchanged."""
    value: JsonValue = {"messages": [{"role": "user", "content": "hello"}]}
    type_id = OpenIdentifier("openai.chat.request")
    payload = JsonPayload(type_id, value, "openai.chat.request")

    # Subtyping is the runtime alignment: the adapter stores an erased value,
    # and the JSON contract must not require a second envelope conversion.
    assert isinstance(payload, ErasedRuntimeValue)
    assert not isinstance(
        ErasedRuntimeValue(type_id, value, "openai.chat.request"),
        JsonPayload,
    )
    assert [field.name for field in fields(JsonPayload)] == [
        "type_id",
        "value",
        "schema_id",
    ]
    request_plan = ProtocolRequestPlan(payload, _execution_plan())
    assert request_plan.payload is payload
    assert request_plan.payload.value is value
    assert payload.value_as(dict) is value


def test_json_payload_rejects_non_json_erased_representations() -> None:
    """Verify widened runtime objects cannot enter the JSON port."""
    type_id = OpenIdentifier("json.rejected")
    private_marker = "private-payload-marker"
    cyclic: list[JsonValue] = []
    cyclic.append(cyclic)
    rejected_values = (
        b"bytes",
        _NativePayload(),
        ("tuple",),
        bytearray(b"buffer"),
        {1: private_marker},
        cyclic,
    )

    for value in rejected_values:
        # The public message identifies the port failure and must not echo the
        # rejected object, which may contain private payload data.
        error = _assert_raises(
            TypeError,
            lambda value=value: JsonPayload(type_id, cast(JsonValue, value)),
            "structurally valid JsonValue",
        )
        assert private_marker not in str(error)
        assert "_NativePayload" not in str(error)


def test_json_payload_rejects_non_portable_numbers_without_exposing_them() -> None:
    """Verify unsafe integers and non-finite floats fail as numeric policy."""
    type_id = OpenIdentifier("json.number")
    unsafe_integer = 2**53
    non_finite = float("nan")

    integer_error = _assert_raises(
        ValueError,
        lambda: JsonPayload(type_id, unsafe_integer),
        "portable JSON numbers",
    )
    float_error = _assert_raises(
        ValueError,
        lambda: JsonPayload(type_id, non_finite),
        "portable JSON numbers",
    )
    _assert_raises(
        ValueError,
        lambda: JsonPayload(type_id, float("inf")),
        "portable JSON numbers",
    )
    _assert_raises(
        ValueError,
        lambda: JsonPayload(type_id, float("-inf")),
        "portable JSON numbers",
    )

    # Boundary values that remain interoperable are still accepted, and neither
    # failure diagnostic includes the rejected numeric text.
    assert JsonPayload(type_id, 2**53 - 1).value == 2**53 - 1
    assert JsonPayload(type_id, -(2**53 - 1)).value == -(2**53 - 1)
    assert JsonPayload(type_id, 0.5).value == 0.5
    assert str(unsafe_integer) not in str(integer_error)
    assert "nan" not in str(float_error).lower()


def test_json_payload_rejects_invalid_port_metadata() -> None:
    """Verify dynamic callers cannot bypass erased metadata shapes."""
    value: JsonValue = {"ok": True}

    # Metadata failures stay on the erased contract and are reported before the
    # JSON value walk replaces them with a value-port error.
    _assert_raises(
        TypeError,
        lambda: JsonPayload(cast(OpenIdentifier, "json.object"), value),
        "type_id must be an OpenIdentifier",
    )
    _assert_raises(
        TypeError,
        lambda: JsonPayload(
            OpenIdentifier("json.object"),
            value,
            cast(str, 1),
        ),
        "schema_id must be a string or None",
    )


def test_json_payload_freezes_the_envelope_without_copying_json() -> None:
    """Verify port facts are immutable while the JSON object keeps identity."""
    items: list[JsonValue] = ["first"]
    value: dict[str, JsonValue] = {"items": items}
    payload = JsonPayload(OpenIdentifier("json.object"), value)

    # The caller retains the mutable JSON container. Freezing only the envelope
    # matches the erased carrier and avoids a hidden copy of the payload.
    items.append("second")
    assert payload.value == {"items": ["first", "second"]}
    assert payload != JsonPayload(payload.type_id, payload.value)
    assert payload == payload
    _assert_raises(
        FrozenInstanceError,
        lambda: payload.__setattr__("schema_id", "changed"),
        "cannot assign to field",
    )


def test_json_payload_narrows_an_erased_port_without_reconstructing_itself() -> None:
    """Verify erased JSON can be narrowed and an existing payload is retained."""
    value: JsonValue = ["kept"]
    type_id = OpenIdentifier("json.array")
    erased = ErasedRuntimeValue(type_id, value, "schema://json/array")
    payload = JsonPayload.from_erased(erased)
    already_frozen = JsonPayload(type_id, value)

    # Narrowing preserves the three port facts and the JSON object. Repeating
    # the narrowing on a JsonPayload must not allocate a replacement envelope.
    assert payload is not erased
    assert isinstance(payload, JsonPayload)
    assert payload.type_id is type_id
    assert payload.schema_id == "schema://json/array"
    assert payload.value is value
    assert JsonPayload.from_erased(already_frozen) is already_frozen
    _assert_raises(
        TypeError,
        lambda: JsonPayload.from_erased(cast(ErasedRuntimeValue, _NativePayload())),
        "source must be an ErasedRuntimeValue",
    )
    _assert_raises(
        TypeError,
        lambda: JsonPayload.from_erased(ErasedRuntimeValue(type_id, _NativePayload())),
        "structurally valid JsonValue",
    )
