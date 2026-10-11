"""Tests that HTTP response bodies are counted chunk by chunk."""

from collections.abc import Callable, Iterator
from typing import cast

from mconet.core.domain import ModelInteractionError, OpenIdentifier
from mconet.transport.http_system import read_bounded_http_response_body

_MAXIMUM_BODY_BYTES = 4


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> BaseException:
    """Return the expected exception after checking its stable message fragment."""
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return error
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_read_bounded_http_response_body_copies_chunks_that_fit() -> None:
    """Verify accepted chunks are copied in source order, including an exact fit."""
    first = b"\x01\x02"
    second = b"\x03\x04"

    body = read_bounded_http_response_body((first, second), _MAXIMUM_BODY_BYTES)

    assert body == b"\x01\x02\x03\x04"
    assert body is not first
    assert read_bounded_http_response_body((), _MAXIMUM_BODY_BYTES) == b""
    assert read_bounded_http_response_body((b"\x01", b"", b"\x02"), 2) == b"\x01\x02"


def test_read_bounded_http_response_body_stops_at_the_oversized_chunk() -> None:
    """Verify the failing chunk is not kept and later chunks are not pulled."""
    reads = 0

    def chunks() -> Iterator[bytes]:
        nonlocal reads
        reads += 1
        yield b"\x01\x02"
        reads += 1
        yield b"\x03\x04\x05"
        reads += 1
        raise AssertionError("reader pulled past the failing chunk")

    error = _assert_raises(
        ModelInteractionError,
        lambda: read_bounded_http_response_body(chunks(), _MAXIMUM_BODY_BYTES),
        "exceeds its byte limit",
    )

    interaction_error = cast(ModelInteractionError, error)
    assert reads == 2
    assert interaction_error.code == "response_body_too_large"
    assert interaction_error.category.id == OpenIdentifier("network")
    assert interaction_error.phase.id == OpenIdentifier("transport")
    assert "\x03" not in str(interaction_error)
    assert "5" not in str(interaction_error)
    assert interaction_error.cause is None


def test_read_bounded_http_response_body_rejects_a_bad_limit_before_reading() -> None:
    """Verify an unusable limit does not pull the first chunk."""
    reads = 0

    def chunks() -> Iterator[bytes]:
        nonlocal reads
        reads += 1
        yield b"\x01"

    for limit in (0, -1, cast(int, 1.5), cast(int, True), 2**53):
        reads = 0
        error = _assert_raises(
            ModelInteractionError,
            lambda limit=limit: read_bounded_http_response_body(chunks(), limit),
            "positive safe integer",
        )
        interaction_error = cast(ModelInteractionError, error)
        assert reads == 0
        assert interaction_error.code == "invalid_component_configuration"
        assert interaction_error.phase.id == OpenIdentifier("transport")
        assert str(limit) not in str(interaction_error)


def test_read_bounded_http_response_body_rejects_a_chunk_that_is_not_bytes() -> None:
    """Verify a mutable buffer is not copied or described in the error."""

    def chunks() -> Iterator[bytes]:
        yield cast(bytes, bytearray(b"\x07\x08"))
        raise AssertionError("reader continued after a non-bytes chunk")

    _assert_raises(
        TypeError,
        lambda: read_bounded_http_response_body(chunks(), _MAXIMUM_BODY_BYTES),
        "chunk must be bytes",
    )
