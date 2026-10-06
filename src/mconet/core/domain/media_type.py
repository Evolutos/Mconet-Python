"""Immutable structured media type values."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

_TOKEN_PUNCTUATION = frozenset("!#$%&'*+-.^_`|~")
_OPTIONAL_WHITESPACE = frozenset((" ", "\t"))


@dataclass(frozen=True, slots=True)
class MediaType:
    """Preserve a media type, subtype, and ordered parameter pairs.

    Syntax, case normalization, quoting, and duplicate-parameter rules belong
    to the parser. The immutable tuple retains the parsed parameter structure
    without exposing mutable mapping behavior.
    """

    type: str
    """The media type token."""

    subtype: str
    """The media subtype token."""

    parameters: tuple[tuple[str, str], ...] = ()
    """Ordered parameter name/value pairs."""

    def __post_init__(self) -> None:
        """Require immutable primitive storage without parsing syntax."""
        media_type = cast(object, self.type)
        subtype = cast(object, self.subtype)
        parameters = cast(object, self.parameters)
        if not isinstance(media_type, str):
            raise TypeError("MediaType type must be a string.")
        if not isinstance(subtype, str):
            raise TypeError("MediaType subtype must be a string.")
        if not isinstance(parameters, tuple):
            raise TypeError("MediaType parameters must be a tuple.")
        for parameter_value in cast(tuple[object, ...], parameters):
            if not isinstance(parameter_value, tuple):
                raise TypeError(
                    "MediaType parameters must contain string name/value pairs."
                )
            parameter = cast(tuple[object, ...], parameter_value)
            if len(parameter) != 2:
                raise TypeError(
                    "MediaType parameters must contain string name/value pairs."
                )
            name, value = parameter
            if not isinstance(name, str) or not isinstance(value, str):
                raise TypeError(
                    "MediaType parameters must contain string name/value pairs."
                )

    def __str__(self) -> str:
        """Return the unparameterized type/subtype form."""
        return f"{self.type}/{self.subtype}"


def parse_media_type(value: str) -> MediaType:
    """Parse an HTTP media type into its canonical structured value.

    Type, subtype, and parameter names are ASCII tokens normalized to lowercase
    because their matching is case-insensitive. Parameter values retain their
    case. Quoted values are decoded by removing the surrounding quotes and each
    quoted-pair escape. Optional spaces or tabs are accepted around parameter
    separators, but whitespace around ``/`` or ``=`` is invalid. Duplicate
    parameter names are rejected case-insensitively.

    Args:
        value: A media type with optional parameters.

    Returns:
        A canonical immutable :class:`MediaType`.

    Raises:
        TypeError: If ``value`` is not a string.
        ValueError: If the media type syntax or a parameter is invalid.
    """
    candidate = cast(object, value)
    if not isinstance(candidate, str):
        raise TypeError("Media type text must be a string.")

    index = _skip_optional_whitespace(candidate, 0)
    media_type, index = _consume_token(candidate, index, "type")
    if index >= len(candidate) or candidate[index] != "/":
        raise ValueError("Media type must contain type/subtype tokens.")

    subtype, index = _consume_token(candidate, index + 1, "subtype")
    index = _skip_optional_whitespace(candidate, index)
    parameters: list[tuple[str, str]] = []
    parameter_names: set[str] = set()

    while index < len(candidate):
        if candidate[index] != ";":
            raise ValueError("Media type contains invalid trailing syntax.")
        index = _skip_optional_whitespace(candidate, index + 1)
        name, index = _consume_token(candidate, index, "parameter name")
        if index >= len(candidate) or candidate[index] != "=":
            raise ValueError("Media type parameter must contain '='.")

        index += 1
        if index < len(candidate) and candidate[index] == '"':
            parameter_value, index = _consume_quoted_string(candidate, index)
        else:
            parameter_value, index = _consume_token(
                candidate,
                index,
                "parameter value",
            )

        normalized_name = name.lower()
        if normalized_name in parameter_names:
            raise ValueError("Media type contains a duplicate parameter name.")
        parameter_names.add(normalized_name)
        parameters.append((normalized_name, parameter_value))
        index = _skip_optional_whitespace(candidate, index)

    return MediaType(media_type.lower(), subtype.lower(), tuple(parameters))


def _skip_optional_whitespace(value: str, index: int) -> int:
    """Advance past HTTP optional whitespace without accepting other controls."""
    while index < len(value) and value[index] in _OPTIONAL_WHITESPACE:
        index += 1
    return index


def _consume_token(value: str, index: int, field: str) -> tuple[str, int]:
    """Consume one non-empty RFC 9110 token from ``index``."""
    start = index
    while index < len(value) and _is_token_character(value[index]):
        index += 1
    if index == start:
        raise ValueError(f"Media type {field} must be a non-empty token.")
    return value[start:index], index


def _is_token_character(character: str) -> bool:
    """Return whether one character belongs to the ASCII HTTP token alphabet."""
    codepoint = ord(character)
    return (
        48 <= codepoint <= 57
        or 65 <= codepoint <= 90
        or 97 <= codepoint <= 122
        or character in _TOKEN_PUNCTUATION
    )


def _consume_quoted_string(value: str, index: int) -> tuple[str, int]:
    """Decode one RFC 9110 quoted-string and its quoted-pair escapes."""
    index += 1
    decoded: list[str] = []
    while index < len(value):
        character = value[index]
        if character == '"':
            return "".join(decoded), index + 1
        if character == "\\":
            index += 1
            if index >= len(value) or not _is_quoted_pair_character(value[index]):
                raise ValueError("Media type contains an invalid quoted-pair.")
            decoded.append(value[index])
            index += 1
            continue
        if not _is_quoted_text_character(character):
            raise ValueError("Media type quoted value contains an invalid character.")
        decoded.append(character)
        index += 1
    raise ValueError("Media type contains an unterminated quoted value.")


def _is_quoted_text_character(character: str) -> bool:
    """Return whether one character can appear unescaped in a quoted-string."""
    codepoint = ord(character)
    return (
        character in _OPTIONAL_WHITESPACE
        or codepoint == 33
        or 35 <= codepoint <= 91
        or 93 <= codepoint <= 126
        or 128 <= codepoint <= 255
    )


def _is_quoted_pair_character(character: str) -> bool:
    """Return whether one character can follow a quoted-pair backslash."""
    codepoint = ord(character)
    return (
        character in _OPTIONAL_WHITESPACE
        or 33 <= codepoint <= 126
        or 128 <= codepoint <= 255
    )
