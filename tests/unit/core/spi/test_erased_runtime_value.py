"""Wrapping and safe retrieval tests for erased runtime values."""

from collections.abc import Callable
from dataclasses import FrozenInstanceError
from typing import cast

from mconet.core.domain import ModelInteractionError, OpenIdentifier
from mconet.core.spi import ErasedRuntimeValue


class _PayloadBase:
    """Base payload type used to verify normal Python subtype retrieval."""


class _Payload(_PayloadBase):
    """Concrete integration-owned payload hidden by the erased wrapper."""

    def __init__(self, text: str) -> None:
        """Store distinguishable mutable payload data for identity tests."""
        # A public field makes later mutation observable and proves the wrapper
        # neither serializes nor defensively copies the native object.
        self.text = text


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> BaseException:
    """Return the expected exception after checking its stable message fragment."""
    try:
        action()
    except exception_type as error:
        # Stable fragments distinguish the intended boundary failure from an
        # unrelated error raised by the test fixture or Python runtime.
        assert message in str(error)
        return error
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_erased_runtime_value_preserves_metadata_and_native_identity() -> None:
    """Verify type ID, Schema ID, and wrapped object remain exact."""
    type_id = OpenIdentifier("protocol.vendor_request")
    payload = _Payload("original")

    erased = ErasedRuntimeValue(type_id, payload, "schema://vendor/request-v1")

    # The carrier exposes portable metadata but retains the platform object by
    # identity, with no conversion into JsonValue or another serialization form.
    assert erased.type_id is type_id
    assert erased.schema_id == "schema://vendor/request-v1"
    assert erased.value is payload


def test_erased_runtime_value_supports_any_native_object_and_optional_schema() -> None:
    """Verify None and mutable values can be wrapped without a Schema ID."""
    mutable_payload = {"segments": ["first"]}
    erased_mutable = ErasedRuntimeValue(
        OpenIdentifier("runtime.mutable"), mutable_payload
    )
    erased_none = ErasedRuntimeValue(OpenIdentifier("runtime.none"), None)

    # Mutability stays owned by the integration: the immutable wrapper prevents
    # field replacement but deliberately does not freeze or copy native state.
    mutable_payload["segments"].append("second")
    assert erased_mutable.value is mutable_payload
    assert erased_mutable.value == {"segments": ["first", "second"]}
    assert erased_mutable.schema_id is None
    assert erased_none.value is None


def test_erased_runtime_value_retrieves_exact_and_base_types() -> None:
    """Verify safe retrieval returns the same object with subtype semantics."""
    payload = _Payload("value")
    erased = ErasedRuntimeValue(OpenIdentifier("protocol.payload"), payload)

    # Python consumers can request either the concrete type or a supported base
    # contract, and both paths retain the exact payload identity.
    assert erased.value_as(_Payload) is payload
    assert erased.value_as(_PayloadBase) is payload
    assert erased.value_as(object) is payload


def test_erased_runtime_value_normalizes_wrong_type_retrieval() -> None:
    """Verify a native type mismatch becomes the standard component error."""
    private_marker = "private-payload-marker"
    type_id = OpenIdentifier("vendor.private_payload")
    erased = ErasedRuntimeValue(type_id, _Payload(private_marker), "private-schema")

    error = cast(
        ModelInteractionError,
        _assert_raises(
            ModelInteractionError,
            lambda: erased.value_as(bytes),
            "does not match the requested Python type",
        ),
    )

    # Normalized fields identify the boundary without reflecting native class,
    # producer metadata, payload repr, or private payload content.
    assert error.category.id == OpenIdentifier("invalid_component_configuration")
    assert error.phase.id == OpenIdentifier("component_type_validation")
    assert error.code == "component_type_mismatch"
    assert error.status_code is None
    assert error.service_error_code is None
    assert error.request_id is None
    assert error.recovery is None
    assert error.cause is None
    error_text = str(error)
    assert private_marker not in error_text
    assert type_id.value not in error_text
    assert "private-schema" not in error_text
    assert "_Payload" not in error_text


def test_erased_runtime_value_rejects_invalid_metadata_and_retrieval_type() -> None:
    """Verify dynamic callers cannot bypass metadata or expected-type shapes."""
    # Metadata is nominal even though the payload is fully erased, and invalid
    # retrieval arguments fail before Python's isinstance receives them.
    _assert_raises(
        TypeError,
        lambda: ErasedRuntimeValue(cast(OpenIdentifier, "payload"), object()),
        "type_id must be an OpenIdentifier",
    )
    _assert_raises(
        TypeError,
        lambda: ErasedRuntimeValue(
            OpenIdentifier("payload.value"),
            object(),
            cast(str, 1),
        ),
        "schema_id must be a string or None",
    )
    erased = ErasedRuntimeValue(OpenIdentifier("payload.value"), object())
    _assert_raises(
        TypeError,
        lambda: erased.value_as(cast(type[object], "object")),
        "expected_type must be a Python runtime type",
    )


def test_erased_runtime_value_freezes_wrapper_fields_without_value_equality() -> None:
    """Verify carrier metadata is frozen and separate wrappers retain identity."""
    payload = _Payload("shared")
    first = ErasedRuntimeValue(OpenIdentifier("payload.value"), payload)
    second = ErasedRuntimeValue(OpenIdentifier("payload.value"), payload)

    # Runtime carriers are not persistent value records: arbitrary payload
    # equality and hash behavior must not define equality between wrappers.
    assert first is not second
    assert first != second
    _assert_raises(
        FrozenInstanceError,
        lambda: first.__setattr__("schema_id", "changed"),
        "cannot assign to field",
    )
