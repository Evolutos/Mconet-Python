"""Value-semantics tests for immutable Bytes values."""

from typing import assert_type

from mconet.core.domain import Bytes


def test_bytes_support_empty_values_and_octet_sizes() -> None:
    """Verify empty and non-empty sizes count encoded octets, not text units."""
    empty = Bytes(b"")
    encoded = Bytes("中".encode())

    assert_type(empty, Bytes)
    assert len(empty) == 0
    assert len(encoded) == 3


def test_bytes_use_immutable_content_equality() -> None:
    """Verify equality and hashing follow immutable byte content."""
    first = Bytes(bytes((0, 127, 255)))
    same = Bytes(bytes((0, 127, 255)))
    different = Bytes(bytes((0, 127, 254)))

    assert first == same
    assert hash(first) == hash(same)
    assert first != different
    assert not hasattr(first, "__setitem__")


def test_bytes_can_snapshot_mutable_binary_input_explicitly() -> None:
    """Verify conversion to bytes isolates a value from later source mutation."""
    source = bytearray((1, 2, 3))
    value = Bytes(bytes(source))

    source[0] = 9

    assert value == b"\x01\x02\x03"
    assert type(value) is bytes
