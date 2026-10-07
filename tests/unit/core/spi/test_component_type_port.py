"""Value-semantics tests for component type ports."""

from collections.abc import Callable
from dataclasses import FrozenInstanceError
from typing import cast

from mconet.core.domain import MediaType, OpenIdentifier
from mconet.core.spi import ComponentTypePort


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    try:
        action()
    except exception_type as error:
        # Match a stable fragment so each failure identifies the rejected field
        # without coupling the test to exception presentation details.
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_component_type_port_preserves_all_declared_fields() -> None:
    """Verify names, type IDs, schemas, and media types remain exact."""
    type_id = OpenIdentifier("payload.request")
    media_type = MediaType("application", "json", (("profile", "vendor.v1"),))

    port = ComponentTypePort(
        name="requestPayload",
        type_id=type_id,
        schema_id="schema://request/v1",
        media_type=media_type,
    )

    # Identity checks confirm the immutable domain values are retained rather
    # than reconstructed, normalized, or parsed at the component boundary.
    assert port.name == "requestPayload"
    assert port.type_id is type_id
    assert port.schema_id == "schema://request/v1"
    assert port.media_type is media_type


def test_component_type_port_supports_unspecified_representation_metadata() -> None:
    """Verify schema and media type remain independently optional."""
    port = ComponentTypePort("input", OpenIdentifier("value.vendor"))

    # Missing representation metadata means no additional compatibility claim;
    # it must not be replaced with inferred defaults.
    assert port.schema_id is None
    assert port.media_type is None


def test_component_type_port_has_immutable_value_semantics() -> None:
    """Verify equality, hashing, and immutability cover every port field."""
    first = ComponentTypePort(
        "output",
        OpenIdentifier("payload.response"),
        "response-v1",
        MediaType("application", "json"),
    )
    same = ComponentTypePort(
        "output",
        OpenIdentifier("payload.response"),
        "response-v1",
        MediaType("application", "json"),
    )
    different_schema = ComponentTypePort(
        "output",
        OpenIdentifier("payload.response"),
        "response-v2",
        MediaType("application", "json"),
    )

    # Dataclass value semantics make complete contracts safe dictionary keys
    # while ensuring compatibility-relevant changes alter equality.
    assert first == same
    assert hash(first) == hash(same)
    assert first != different_schema
    _assert_raises(
        FrozenInstanceError,
        lambda: first.__setattr__("name", "changed"),
        "cannot assign to field",
    )


def test_component_type_port_rejects_invalid_required_field_shapes() -> None:
    """Verify dynamic callers cannot substitute values for required types."""
    # Exercise each required field independently so nominal type failures remain
    # attributable even when callers bypass static analysis.
    _assert_raises(
        TypeError,
        lambda: ComponentTypePort(cast(str, 1), OpenIdentifier("payload.value")),
        "name must be a string",
    )
    _assert_raises(
        TypeError,
        lambda: ComponentTypePort("input", cast(OpenIdentifier, "payload.value")),
        "type_id must be an OpenIdentifier",
    )


def test_component_type_port_rejects_invalid_optional_field_shapes() -> None:
    """Verify optional metadata accepts only its declared nominal values."""
    # Non-None metadata must retain its declared value-object shape; accepting a
    # loosely typed substitute would defer deterministic contract errors.
    _assert_raises(
        TypeError,
        lambda: ComponentTypePort(
            "input",
            OpenIdentifier("payload.value"),
            schema_id=cast(str, 1),
        ),
        "schema_id must be a string or None",
    )
    _assert_raises(
        TypeError,
        lambda: ComponentTypePort(
            "input",
            OpenIdentifier("payload.value"),
            media_type=cast(MediaType, "application/json"),
        ),
        "media_type must be a MediaType or None",
    )
