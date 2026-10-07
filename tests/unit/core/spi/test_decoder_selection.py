"""Value and boundary tests for payload decoder selection criteria."""

from collections.abc import Callable
from dataclasses import FrozenInstanceError, fields
from typing import cast

from mconet.core.domain import MediaType
from mconet.core.spi import DecoderSelection


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    try:
        action()
    except exception_type as error:
        # Match the owned field diagnostic so an unrelated setup exception cannot
        # make a negative decoder-selection test pass accidentally.
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_decoder_selection_preserves_media_type_and_schema_id() -> None:
    """Verify both planned decoder criteria remain exact and structured."""
    media_type = MediaType(
        "application",
        "vnd.vendor-response+protobuf",
        (("version", "2"),),
    )

    selection = DecoderSelection(media_type, "schema://vendor/response#v2")

    # Structured plan identity and ordered media parameters remain untouched;
    # schema text is not parsed, versioned, or normalized by this value object.
    selected_media_type = selection.media_type
    assert selected_media_type is not None
    assert selected_media_type is media_type
    assert selected_media_type.parameters == (("version", "2"),)
    assert selection.schema_id == "schema://vendor/response#v2"


def test_decoder_selection_supports_independently_optional_criteria() -> None:
    """Verify each planned decoder criterion can be absent independently."""
    media_type = MediaType("application", "problem+json")
    unconstrained = DecoderSelection()
    media_only = DecoderSelection(media_type=media_type)
    schema_only = DecoderSelection(schema_id="schema.vendor.error")

    # Missing criteria remain None rather than adopting the success decoder's
    # conditions or a response Content-Type observed only after network I/O.
    assert unconstrained.media_type is None
    assert unconstrained.schema_id is None
    assert media_only.media_type is media_type
    assert media_only.schema_id is None
    assert schema_only.media_type is None
    assert schema_only.schema_id == "schema.vendor.error"


def test_decoder_selection_has_immutable_value_semantics() -> None:
    """Verify equality, hashing, and frozen fields include both criteria."""
    first = DecoderSelection(MediaType("application", "json"), "schema.response")
    same = DecoderSelection(MediaType("application", "json"), "schema.response")
    different = DecoderSelection(MediaType("application", "problem+json"), None)

    # A hashable immutable snapshot can be resolved before I/O and retained
    # unchanged while actual response metadata is checked for compatibility.
    assert first == same
    assert hash(first) == hash(same)
    assert first != different
    _assert_raises(
        FrozenInstanceError,
        lambda: first.__setattr__("media_type", MediaType("text", "plain")),
        "cannot assign to field",
    )


def test_decoder_selection_exposes_only_pre_io_resolution_criteria() -> None:
    """Verify decoder instances and response observations stay outside selection."""
    selection = DecoderSelection()

    # The exact field surface prevents actual Content-Type, outcome, or a decoder
    # instance from becoming late component-selection inputs after a response.
    assert tuple(field.name for field in fields(DecoderSelection)) == (
        "media_type",
        "schema_id",
    )
    assert not hasattr(selection, "decoder")
    assert not hasattr(selection, "actual_media_type")
    assert not hasattr(selection, "outcome")


def test_decoder_selection_requires_structured_media_type() -> None:
    """Verify raw response types and unrelated values cannot replace MediaType."""
    # Parsing an actual Content-Type belongs to transport response mapping and
    # compatibility checking, not to the pre-I/O decoder selection value.
    invalid_values: tuple[object, ...] = ("application/json", {}, object())
    for value in invalid_values:
        _assert_raises(
            TypeError,
            lambda value=value: DecoderSelection(media_type=cast(MediaType, value)),
            "media_type must be a MediaType or None",
        )


def test_decoder_selection_requires_optional_schema_text() -> None:
    """Verify non-string dynamic values cannot act as schema identities."""
    # Schema semantics remain open, but numeric, collection, and arbitrary-object
    # substitutes are never coerced into planned decoder contract text.
    invalid_values: tuple[object, ...] = (1, [], object())
    for value in invalid_values:
        _assert_raises(
            TypeError,
            lambda value=value: DecoderSelection(schema_id=cast(str, value)),
            "schema_id must be a string or None",
        )
