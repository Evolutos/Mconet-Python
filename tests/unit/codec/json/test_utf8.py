"""UTF-8 encoding tests for scalar values and illegal surrogates."""

from collections.abc import Callable
from typing import cast

from mconet.codec.json import encode_utf8
from mconet.core.domain import Bytes

_REPLACEMENT_UTF8 = bytes((0xEF, 0xBF, 0xBD))


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    try:
        action()
    except exception_type as error:
        # The fragment distinguishes a type-boundary failure from an unexpected
        # Unicode encode error.
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_encode_utf8_encodes_empty_bmp_non_bmp_and_emoji_text() -> None:
    """Verify the required scalar cases use standard UTF-8 bytes."""
    # Empty text is a real payload, not a missing value. Non-BMP scalars and
    # emoji must be encoded as their Unicode scalar values, not as surrogate
    # code units.
    assert encode_utf8("") == b""
    assert encode_utf8("A") == b"A"
    assert encode_utf8("é") == bytes((0xC3, 0xA9))
    assert encode_utf8("𐀀") == bytes((0xF0, 0x90, 0x80, 0x80))
    assert encode_utf8("😀") == bytes((0xF0, 0x9F, 0x98, 0x80))
    assert encode_utf8("A𐀀😀") == bytes(
        (0x41, 0xF0, 0x90, 0x80, 0x80, 0xF0, 0x9F, 0x98, 0x80)
    )
    assert isinstance(encode_utf8("A"), bytes)


def test_encode_utf8_replaces_surrogate_code_points_with_ufffd() -> None:
    """Verify illegal surrogates become U+FFFD and are not emitted as UTF-8."""
    lone_high = "\ud800"
    lone_low = "\udc00"
    pair = "\ud800\udc00"
    surrounded = "A\ud800B"

    # Each surrogate code point is replaced independently. Adjacent surrogates
    # stay two code points because a Python string is not a UTF-16 buffer.
    assert encode_utf8(lone_high) == _REPLACEMENT_UTF8
    assert encode_utf8(lone_low) == _REPLACEMENT_UTF8
    assert encode_utf8(pair) == _REPLACEMENT_UTF8 + _REPLACEMENT_UTF8
    assert encode_utf8(surrounded) == b"A" + _REPLACEMENT_UTF8 + b"B"
    assert bytes((0xED, 0xA0, 0x80)) not in encode_utf8(lone_high)


def test_encode_utf8_returns_new_bytes_and_rejects_non_strings() -> None:
    """Verify callers receive an independent Bytes value."""
    first = encode_utf8("hello")
    second = encode_utf8("hello")

    # Equal contents do not share storage for this value. A non-string cannot
    # be encoded by guessing its text representation.
    assert first == second
    assert first is not second
    assert encode_utf8("A") == Bytes(b"A")
    _assert_raises(
        TypeError,
        lambda: encode_utf8(cast(str, b"A")),
        "text must be a string",
    )
