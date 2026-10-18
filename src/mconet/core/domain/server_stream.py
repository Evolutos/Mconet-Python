"""Single-consumption iterator for one opened server stream."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from typing import cast

from mconet.core.domain.error_category import ErrorCategory
from mconet.core.domain.interaction_phase import InteractionPhase
from mconet.core.domain.model_interaction_error import ModelInteractionError
from mconet.core.domain.open_identifier import OpenIdentifier
from mconet.core.domain.server_stream_event import ServerStreamEvent

_INVALID_REQUEST = ErrorCategory(OpenIdentifier("invalid_request"))
_STREAM_MAPPING = InteractionPhase(OpenIdentifier("stream_mapping"))
_CONSUMED_CODE = "stream_events_consumed"
_CONSUMED_MESSAGE = "The server stream was already consumed."


class ServerStream:
    """Yield the events of one server stream and then refuse a second read.

    The iterator is created only after the request has been authorized and the
    response headers have been accepted. Reading it pulls framed events.
    Closing it aborts the underlying exchange. A second iteration fails with
    ``stream_events_consumed`` instead of replaying or reopening the body.
    """

    __slots__ = ("_close", "_consumed", "_events")

    def __init__(
        self,
        events: AsyncIterator[ServerStreamEvent],
        close: Callable[[], None],
    ) -> None:
        """Retain the event source and the one-shot closer.

        Args:
            events: Framed events. This object does not start them until
                iteration.
            close: Releases the exchange. It must be safe to call more than
                once.

        Raises:
            TypeError: If ``events`` is not an async iterator or ``close`` is
                not callable.
        """
        candidate = cast(object, events)
        closer = cast(object, close)
        # An async iterator is the only source that can produce events without
        # this object knowing the transport. A plain iterable would hide that
        # the body is still arriving.
        if not hasattr(candidate, "__aiter__"):
            raise TypeError("events must be an async iterator.")
        if not callable(closer):
            raise TypeError("close must be callable.")
        self._events = events
        self._close = close
        self._consumed = False

    def __aiter__(self) -> AsyncIterator[ServerStreamEvent]:
        """Return the event source the first time, and fail after that."""
        # The flag flips before the body is read so a second loop cannot start
        # even if the first loop has not yet pulled an event.
        if self._consumed:
            raise _consumed_error()
        self._consumed = True
        return self._events

    async def aclose(self) -> None:
        """Release the exchange without reading any further events."""
        # Close is synchronous because it only aborts the socket and drops
        # already retained interaction state. It does not wait for a new read.
        self._close()

    def __del__(self) -> None:
        """Release the exchange if the caller never closes or finishes it."""
        # Best-effort only. A caller that iterates or awaits aclose has already
        # released the exchange; a second close is a no-op. Failures during
        # garbage collection must not surface as an unraisable exception.
        closer = getattr(self, "_close", None)
        if closer is None:
            return
        try:
            closer()
        except Exception:
            return


def _consumed_error() -> ModelInteractionError:
    """Create the failure for a stream that has already been iterated."""
    # The message names the lifecycle rule only. It does not include events,
    # request text, or connection details.
    return ModelInteractionError(
        category=_INVALID_REQUEST,
        phase=_STREAM_MAPPING,
        code=_CONSUMED_CODE,
        message=_CONSUMED_MESSAGE,
    )
