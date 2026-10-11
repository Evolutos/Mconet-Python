"""UTF-8 text encoding for the JSON codec."""

from __future__ import annotations

from typing import cast

from mconet.core.domain import Bytes

_SURROGATE_MIN = 0xD800
_SURROGATE_MAX = 0xDFFF
_REPLACEMENT_CHARACTER = "\ufffd"


def encode_utf8(text: str) -> Bytes:
    """Encode one string as a new UTF-8 byte sequence.

    Supplementary-plane scalars and emoji use Python's standard UTF-8 mapping.
    An empty string is valid and produces an empty byte sequence. Surrogate
    code points are not Unicode scalar values, so each one is replaced with
    U+FFFD before encoding. They are not joined into a pair and are not written
    with the ill-formed UTF-8 bytes that ``surrogatepass`` would emit.

    The function does not serialize JSON, inspect a payload, or retain the
    input. The result is an immutable :data:`Bytes` value. A one-byte result
    may be interned by the runtime; longer results are independent objects.

    Args:
        text: Unicode text to encode.

    Returns:
        Newly allocated UTF-8 octets for ``text``.

    Raises:
        TypeError: If ``text`` is not a string.
    """
    candidate = cast(object, text)
    if not isinstance(candidate, str):
        raise TypeError("text must be a string.")

    # Python strings already store non-BMP characters as scalar values. Only
    # isolated surrogate code points need a policy before the strict encoder.
    scalars = _replace_surrogate_code_points(candidate)
    # strict is the default. After replacement, encoding cannot raise for
    # surrogates, and errors="replace" would emit "?" rather than U+FFFD.
    return Bytes(scalars.encode("utf-8"))


def _replace_surrogate_code_points(text: str) -> str:
    """Return text with every surrogate code point replaced by U+FFFD.

    Args:
        text: A confirmed string, which may contain isolated surrogate code
            points.

    Returns:
        The original string when it contains no surrogates. Otherwise a new
        string whose surrogate code points are U+FFFD.
    """
    # Ordinary payload text should not pay for a copied string. The scan also
    # avoids interpreting two adjacent surrogates as one UTF-16 scalar, because
    # a Python string is not a UTF-16 code-unit buffer.
    if not any(
        _SURROGATE_MIN <= ord(character) <= _SURROGATE_MAX for character in text
    ):
        return text
    return "".join(
        _REPLACEMENT_CHARACTER
        if _SURROGATE_MIN <= ord(character) <= _SURROGATE_MAX
        else character
        for character in text
    )
