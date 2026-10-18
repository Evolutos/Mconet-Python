"""Server-sent-event framing for one server-stream response body."""

from __future__ import annotations

from collections.abc import AsyncIterable, AsyncIterator

from mconet.core.domain.error_category import ErrorCategory
from mconet.core.domain.interaction_phase import InteractionPhase
from mconet.core.domain.model_interaction_error import ModelInteractionError
from mconet.core.domain.open_identifier import OpenIdentifier

_PROTOCOL = ErrorCategory(OpenIdentifier("protocol"))
_NETWORK = ErrorCategory(OpenIdentifier("network"))
_FRAMING = InteractionPhase(OpenIdentifier("stream_framing"))
_TRANSPORT = InteractionPhase(OpenIdentifier("transport"))
_FRAME_CODE = "stream_frame_too_large"
_FRAME_MESSAGE = "A stream frame exceeds its byte limit."
_BODY_CODE = "response_body_too_large"
_BODY_MESSAGE = "HTTP response body exceeds its byte limit."
_INCOMPLETE_CODE = "incomplete_stream_frame"
_INCOMPLETE_MESSAGE = "The server stream ended inside an event."
_DONE = b"[DONE]"


async def iter_sse_payloads(
    chunks: AsyncIterable[object],
    *,
    max_frame_bytes: int,
    max_body_bytes: int,
) -> AsyncIterator[bytes | None]:
    """Yield one SSE data payload at a time, then ``None`` at the end.

    Events are separated by a blank line. ``data`` fields in one event are
    joined with a newline, and a single leading space after the colon is
    removed. Comment lines are ignored. The payload ``[DONE]`` ends the
    stream. A clean close without that marker still yields ``None``.

    Args:
        chunks: Response body chunks in arrival order.
        max_frame_bytes: Maximum encoded size of one event, including its
            field lines and the blank line that ends it.
        max_body_bytes: Maximum total body size across every chunk.

    Yields:
        The data payload of each event. ``None`` is the terminal marker and
        is yielded once.

    Raises:
        TypeError: If a chunk is not ``bytes`` or a limit is not an integer.
        ModelInteractionError: If a frame or the body exceeds its limit, or
            the body ends inside an event. Frame failures use
            ``stream_frame_too_large``. Body failures use
            ``response_body_too_large``. A partial trailing event uses
            ``incomplete_stream_frame``.
    """
    if type(max_frame_bytes) is not int or type(max_body_bytes) is not int:
        raise TypeError("stream byte limits must be integers.")
    # The limits are already resolved to positive values. A non-positive
    # limit cannot describe a frame, so it fails before any byte is parsed.
    if max_frame_bytes <= 0 or max_body_bytes <= 0:
        raise ValueError("stream byte limits must be positive.")
    pending = bytearray()
    data_lines: list[bytes] = []
    event_bytes = 0
    body_bytes = 0
    async for chunk_value in chunks:
        # The annotation is object so a transport that yields a non-bytes
        # chunk fails here instead of being treated as a frame.
        if not isinstance(chunk_value, bytes):
            raise TypeError("stream chunk must be bytes.")
        chunk = chunk_value
        body_bytes += len(chunk)
        # The body limit counts octets as they arrive, before a line is
        # complete, so a stream cannot grow past the configured budget.
        if body_bytes > max_body_bytes:
            raise _body_too_large()
        pending.extend(chunk)
        while True:
            taken = _take_line(pending)
            if taken is None:
                # An unfinished line still belongs to the current event. Count
                # it now so a single huge line fails before the buffer grows
                # without a bound.
                if event_bytes + len(pending) > max_frame_bytes:
                    raise _frame_too_large()
                break
            line, consumed = taken
            del pending[:consumed]
            event_bytes += consumed
            if event_bytes > max_frame_bytes:
                raise _frame_too_large()
            if line == b"":
                # A blank line dispatches the event. Comment-only events have
                # no data and are discarded without becoming a payload.
                if data_lines:
                    payload = b"\n".join(data_lines)
                    data_lines = []
                    event_bytes = 0
                    if payload == _DONE:
                        yield None
                        return
                    yield payload
                else:
                    event_bytes = 0
                continue
            # A colon-led line is a comment. Other fields, such as event and
            # id, are not part of the model payload.
            if line.startswith(b":"):
                continue
            name, value = _split_field(line)
            if name == b"data":
                data_lines.append(value)
    # Bytes left after the last chunk were not a complete event. Dispatching
    # them would invent a frame the service did not finish.
    if pending or data_lines:
        raise _incomplete_frame()
    yield None


def _take_line(buffer: bytearray) -> tuple[bytes, int] | None:
    """Return one complete line and the number of buffer bytes it occupied."""
    # SSE accepts LF, CR, and CR LF. A trailing CR stays buffered until the
    # next byte shows whether it is the start of CR LF.
    for index, byte in enumerate(buffer):
        if byte == 10:
            return bytes(buffer[:index]), index + 1
        if byte != 13:
            continue
        if index + 1 == len(buffer):
            return None
        if buffer[index + 1] == 10:
            return bytes(buffer[:index]), index + 2
        return bytes(buffer[:index]), index + 1
    return None


def _split_field(line: bytes) -> tuple[bytes, bytes]:
    """Split one SSE field into a name and a value."""
    # The first colon separates the name. One leading space in the value is
    # the optional SSE padding and is not part of the payload.
    colon = line.find(b":")
    if colon < 0:
        return line, b""
    value = line[colon + 1 :]
    if value.startswith(b" "):
        value = value[1:]
    return line[:colon], value


def _frame_too_large() -> ModelInteractionError:
    """Create the failure for one event that exceeds the frame limit."""
    # The frame bytes are not copied into the message.
    return ModelInteractionError(
        category=_PROTOCOL,
        phase=_FRAMING,
        code=_FRAME_CODE,
        message=_FRAME_MESSAGE,
    )


def _body_too_large() -> ModelInteractionError:
    """Create the failure for a stream body that exceeds its limit."""
    # The accumulated length stays out of the message.
    return ModelInteractionError(
        category=_NETWORK,
        phase=_TRANSPORT,
        code=_BODY_CODE,
        message=_BODY_MESSAGE,
    )


def _incomplete_frame() -> ModelInteractionError:
    """Create the failure for a body that ends inside an event."""
    # The partial line is not included. It can contain response text.
    return ModelInteractionError(
        category=_PROTOCOL,
        phase=_FRAMING,
        code=_INCOMPLETE_CODE,
        message=_INCOMPLETE_MESSAGE,
    )
