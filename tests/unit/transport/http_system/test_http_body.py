"""Tests that HTTP body writing keeps empty and binary octets intact."""

from collections.abc import Callable
from typing import cast

from mconet.core.domain import Bytes, MediaType
from mconet.core.spi import TransportBody
from mconet.transport.http_system import map_http_body


def _body(payload: bytes) -> TransportBody:
    """Build a body without inspecting or decoding its octets."""
    return TransportBody(Bytes(payload), MediaType("application", "octet-stream"))


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_map_http_body_returns_empty_and_binary_bytes_unchanged() -> None:
    """Verify empty and non-text octets are not decoded or replaced."""
    empty = _body(b"")
    binary = _body(b"\x00\xff\xfe\r\nnot-text")

    assert map_http_body(empty) is empty.bytes
    assert map_http_body(binary) is binary.bytes
    assert map_http_body(empty) == b""
    assert isinstance(map_http_body(binary), bytes)
    assert not isinstance(map_http_body(binary), str)
    assert b"\xff\xfe" in map_http_body(binary)


def test_map_http_body_rejects_non_body_values() -> None:
    """Verify text is not accepted in place of a transport body."""
    _assert_raises(
        TypeError,
        lambda: map_http_body(cast(TransportBody, "hello")),
        "body must be a TransportBody",
    )
