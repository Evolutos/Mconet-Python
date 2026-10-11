"""Limit and stop tests for bounded response body collection."""

from collections.abc import Callable, Iterator
from typing import cast

from mconet.codec.json import collect_bounded_bytes
from mconet.core.domain import ModelInteractionError, OpenIdentifier

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
        # The fragment identifies the collection failure without accepting an
        # unrelated fixture error.
        assert message in str(error)
        return error
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_collect_bounded_bytes_copies_chunks_that_fit_in_order() -> None:
    """Verify accepted chunks are copied in source order."""
    first = b"\x01\x02"
    second = b"\x03\x04"

    body = collect_bounded_bytes((first, second), _MAXIMUM_BODY_BYTES)

    # The result is a new bytes value containing only the supplied chunks.
    assert body == b"\x01\x02\x03\x04"
    assert body is not first
    assert collect_bounded_bytes((b"\x01\x02\x03\x04",), _MAXIMUM_BODY_BYTES) == (
        b"\x01\x02\x03\x04"
    )


def test_collect_bounded_bytes_keeps_bytes_after_an_empty_chunk() -> None:
    """Verify a zero-length chunk does not end the body."""
    body = collect_bounded_bytes((b"\x01", b"", b"\x02"), _MAXIMUM_BODY_BYTES)

    # An empty chunk is present input. The following chunk is still collected.
    assert body == b"\x01\x02"
    assert collect_bounded_bytes((), _MAXIMUM_BODY_BYTES) == b""


def test_collect_bounded_bytes_copies_only_a_slice_that_was_supplied() -> None:
    """Verify bytes outside the supplied slice are not part of the body."""
    buffer = b"\x09\x01\x02\x09"
    view = buffer[1:3]

    # The collector sees the slice the caller passed, not the neighboring bytes
    # in the original buffer.
    assert collect_bounded_bytes((view,), _MAXIMUM_BODY_BYTES) == b"\x01\x02"


def test_collect_bounded_bytes_stops_before_reading_past_an_oversized_chunk() -> None:
    """Verify the failing chunk is not kept and later chunks are not read."""
    reads = 0

    def chunks() -> Iterator[bytes]:
        nonlocal reads
        reads += 1
        yield b"\x01\x02"
        reads += 1
        yield b"\x03\x04\x05"
        reads += 1
        raise AssertionError("collector read past the failing chunk")

    error = _assert_raises(
        ModelInteractionError,
        lambda: collect_bounded_bytes(chunks(), _MAXIMUM_BODY_BYTES),
        "exceeds its byte limit",
    )

    # The second read is the chunk that does not fit. Its bytes and every later
    # chunk stay unread by the returned error.
    interaction_error = cast(ModelInteractionError, error)
    assert reads == 2
    assert interaction_error.code == "response_body_too_large"
    assert interaction_error.category.id == OpenIdentifier("deserialization")
    assert interaction_error.phase.id == OpenIdentifier("decoding")
    assert "\x03" not in str(interaction_error)
    assert interaction_error.cause is None


def test_collect_bounded_bytes_omits_source_bytes_from_the_size_error() -> None:
    """Verify an oversized chunk is absent from the diagnostic."""
    secret_byte = 7
    error = _assert_raises(
        ModelInteractionError,
        lambda: collect_bounded_bytes((bytes((secret_byte, secret_byte)),), 1),
        "exceeds its byte limit",
    )

    assert str(secret_byte) not in str(error)


def test_collect_bounded_bytes_rejects_an_unusable_limit_before_reading() -> None:
    """Verify a bad limit does not consume the first chunk."""
    reads = 0

    def chunks() -> Iterator[bytes]:
        nonlocal reads
        reads += 1
        yield b"\x01"

    for limit in (0, -1, cast(int, 1.5), cast(int, True), 2**53):
        reads = 0
        error = _assert_raises(
            ModelInteractionError,
            lambda limit=limit: collect_bounded_bytes(chunks(), limit),
            "positive safe integer",
        )
        interaction_error = cast(ModelInteractionError, error)
        # No chunk is pulled, and the rejected limit value is not part of the
        # diagnostic text.
        assert reads == 0
        assert interaction_error.code == "invalid_component_configuration"
        assert interaction_error.category.id == OpenIdentifier(
            "invalid_component_configuration"
        )
        assert str(limit) not in str(interaction_error)


def test_collect_bounded_bytes_rejects_a_chunk_that_is_not_bytes() -> None:
    """Verify a mutable buffer is not copied or described in the error."""

    def chunks() -> Iterator[bytes]:
        yield cast(bytes, bytearray(b"\x01"))

    error = _assert_raises(
        ModelInteractionError,
        lambda: collect_bounded_bytes(chunks(), _MAXIMUM_BODY_BYTES),
        "chunk must be bytes",
    )
    interaction_error = cast(ModelInteractionError, error)
    assert interaction_error.code == "deserialization"
    assert "bytearray" not in str(interaction_error)
