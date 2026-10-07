"""Value and boundary tests for payload encoder selection criteria."""

from collections.abc import Callable
from dataclasses import FrozenInstanceError, fields
from typing import cast

from mconet.core.domain import MediaType
from mconet.core.spi import EncoderSelection


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    try:
        action()
    except exception_type as error:
        # Match a stable field diagnostic so an unrelated construction failure
        # cannot make a negative selection test appear successful.
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_encoder_selection_preserves_media_type_and_schema_id() -> None:
    """Verify both encoder criteria remain exact and structured."""
    media_type = MediaType(
        "application",
        "vnd.vendor+json",
        (("profile", "compact"),),
    )

    selection = EncoderSelection(media_type, "schema://vendor/request#v2")

    # MediaType identity and ordered parameters survive unchanged, while schema
    # text is neither parsed nor normalized by the selection container.
    selected_media_type = selection.media_type
    assert selected_media_type is not None
    assert selected_media_type is media_type
    assert selected_media_type.parameters == (("profile", "compact"),)
    assert selection.schema_id == "schema://vendor/request#v2"


def test_encoder_selection_supports_independently_optional_criteria() -> None:
    """Verify each criterion can be omitted without inventing a fallback."""
    media_type = MediaType("application", "json")
    unconstrained = EncoderSelection()
    media_only = EncoderSelection(media_type=media_type)
    schema_only = EncoderSelection(schema_id="schema.vendor.request")

    # Absence remains None instead of a wildcard string or default JSON type;
    # the resolver later determines whether the remaining candidates are unique.
    assert unconstrained.media_type is None
    assert unconstrained.schema_id is None
    assert media_only.media_type is media_type
    assert media_only.schema_id is None
    assert schema_only.media_type is None
    assert schema_only.schema_id == "schema.vendor.request"


def test_encoder_selection_has_immutable_value_semantics() -> None:
    """Verify equality, hashing, and frozen fields include both criteria."""
    first = EncoderSelection(MediaType("application", "json"), "schema.request")
    same = EncoderSelection(MediaType("application", "json"), "schema.request")
    different = EncoderSelection(MediaType("application", "json"), None)

    # Both selection facts form one hashable snapshot that cannot change while
    # component resolution evaluates compatible candidates.
    assert first == same
    assert hash(first) == hash(same)
    assert first != different
    _assert_raises(
        FrozenInstanceError,
        lambda: first.__setattr__("schema_id", "changed"),
        "cannot assign to field",
    )


def test_encoder_selection_exposes_only_resolution_criteria() -> None:
    """Verify component identity and capabilities stay outside this value."""
    selection = EncoderSelection()

    # The exact field surface prevents protocol planning from prematurely naming
    # an encoder, storing its descriptor, or duplicating capability requirements.
    assert tuple(field.name for field in fields(EncoderSelection)) == (
        "media_type",
        "schema_id",
    )
    assert not hasattr(selection, "component_id")
    assert not hasattr(selection, "encoder")
    assert not hasattr(selection, "capabilities")


def test_encoder_selection_requires_structured_media_type() -> None:
    """Verify raw strings and unrelated objects cannot replace MediaType."""
    # Parsing stays explicit upstream; selection cannot silently normalize a raw
    # header value or infer a representation from an arbitrary object.
    invalid_values: tuple[object, ...] = ("application/json", {}, object())
    for value in invalid_values:
        _assert_raises(
            TypeError,
            lambda value=value: EncoderSelection(media_type=cast(MediaType, value)),
            "media_type must be a MediaType or None",
        )


def test_encoder_selection_requires_optional_schema_text() -> None:
    """Verify dynamic callers cannot substitute non-string schema identities."""
    # Schema syntax remains open, but storage is exact text when present; numeric,
    # collection, and arbitrary-object substitutes receive no implicit conversion.
    invalid_values: tuple[object, ...] = (1, [], object())
    for value in invalid_values:
        _assert_raises(
            TypeError,
            lambda value=value: EncoderSelection(schema_id=cast(str, value)),
            "schema_id must be a string or None",
        )
