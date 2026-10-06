"""Semantic validation for immutable text message content."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from mconet.core.domain.json_value import JsonValue, validate_json_value_numbers
from mconet.core.domain.message_content_kind import MessageContentKind
from mconet.core.domain.open_identifier import OpenIdentifier, validate_open_identifier
from mconet.core.domain.text_message_content import TextMessageContent


def validate_text_message_content(
    content: TextMessageContent,
    *,
    maximum_code_points: int | None = None,
) -> TextMessageContent:
    """Validate text content without normalization or an implicit size policy.

    Args:
        content: The immutable text content to validate.
        maximum_code_points: Optional inclusive text length limit measured in
            Unicode code points. ``None`` applies no domain-level length limit.

    Returns:
        The same content object after successful validation.

    Raises:
        TypeError: If the content or validation-limit runtime type is invalid.
        ValueError: If identity, kind, JSON data, or the explicit limit is invalid.

    Notes:
        Empty text is valid. The validator preserves whitespace, line endings,
        emoji, combining sequences, and normalization form exactly as supplied.
        Protocol- or model-specific context limits belong to later integration
        and capability validation rather than becoming a universal text limit.
    """
    candidate = cast(object, content)
    # Require the nominal concrete type because this validator defines the
    # invariants of TextMessageContent rather than every structural content kind.
    if not isinstance(candidate, TextMessageContent):
        raise TypeError("content must be a TextMessageContent.")

    limit = cast(object, maximum_code_points)
    # Exact int checking rejects booleans, whose numeric subclass relationship
    # would otherwise turn True and False into surprising length policies.
    if limit is not None:
        if type(limit) is not int:
            raise TypeError("maximum_code_points must be an integer or None.")
        if limit < 0:
            raise ValueError("maximum_code_points must not be negative.")

    content_id = cast(object, candidate.id)
    text = cast(object, candidate.text)
    # Repeat primitive checks at the trust boundary so dynamically constructed
    # or deserialized instances cannot bypass the declared dataclass annotations.
    if not isinstance(content_id, str):
        raise TypeError("TextMessageContent id must be a string.")
    if not isinstance(text, str):
        raise TypeError("TextMessageContent text must be a string.")

    _validate_text_kind(cast(object, candidate.kind))
    # Python string length counts Unicode code points rather than UTF-8 bytes.
    # Empty text and an exact inclusive boundary pass without special casing.
    if limit is not None and len(text) > limit:
        raise ValueError("TextMessageContent text exceeds maximum_code_points.")

    # Validate both JSON channels independently so errors stay attributable and
    # provider-defined extension keys remain uninterpreted.
    _validate_json_mapping(cast(object, candidate.metadata), "metadata")
    _validate_json_mapping(cast(object, candidate.extensions), "extensions")
    return candidate


def _validate_text_kind(value: object) -> None:
    """Require the fixed, portable ``content.text`` kind identity."""
    # Structural checking catches an overridden or malformed kind property on a
    # dynamic subclass before the validator reads its identifier.
    if not isinstance(value, MessageContentKind):
        raise TypeError("TextMessageContent kind must implement MessageContentKind.")
    identifier = cast(object, value.id)
    if not isinstance(identifier, OpenIdentifier):
        raise TypeError("TextMessageContent kind id must be an OpenIdentifier.")
    validate_open_identifier(identifier)
    # A concrete text value cannot be reclassified as another content payload;
    # rejecting the mismatch prevents mapper selection from becoming ambiguous.
    if identifier.value != "content.text":
        raise ValueError("TextMessageContent kind must be content.text.")


def _validate_json_mapping(value: object, field_name: str) -> None:
    """Require a string-keyed mapping containing portable JSON values."""
    # Public contracts accept any Mapping implementation, while JSON object keys
    # remain strings across every supported language.
    if not isinstance(value, Mapping):
        raise TypeError(f"TextMessageContent {field_name} must be a mapping.")
    mapping = cast(Mapping[object, object], value)
    if any(not isinstance(key, str) for key in mapping):
        raise TypeError(f"TextMessageContent {field_name} keys must be strings.")

    # Validate recursive shape and portable numbers without interpreting unknown
    # metadata or extension semantics.
    for raw_value in mapping.values():
        validate_json_value_numbers(cast(JsonValue, raw_value))
