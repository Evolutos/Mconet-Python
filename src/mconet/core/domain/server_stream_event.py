"""One event yielded by a server-stream model interaction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast


@dataclass(frozen=True, slots=True)
class ServerStreamEvent:
    """Carry one incremental server-stream observation.

    A content event reports the choice index, the text delta, and any finish
    reason the service attached to that same chunk. A terminal event has
    ``done`` set and empty text; it marks the end of the stream and does not
    itself contain a model token. The value stores no socket, buffer, or
    credential.
    """

    index: int
    """Choice index the service assigned to this chunk."""

    text: str
    """Text delta for this chunk. Empty when the chunk has no content."""

    finish_reason: str | None = None
    """Service finish reason, or ``None`` when this chunk does not end generation."""

    response_id: str | None = None
    """Service response identifier, or ``None`` when the chunk omitted it."""

    model: str | None = None
    """Model name reported by the service, or ``None`` when omitted."""

    done: bool = False
    """True only for the terminal event that ends the stream."""

    def __post_init__(self) -> None:
        """Require the event fields to use their declared storage types."""
        index = cast(object, self.index)
        text = cast(object, self.text)
        finish_reason = cast(object, self.finish_reason)
        response_id = cast(object, self.response_id)
        model = cast(object, self.model)
        done = cast(object, self.done)
        # bool is an int subclass, so the index check is exact. A flag must
        # not be stored as a choice position.
        if type(index) is not int:
            raise TypeError("ServerStreamEvent index must be an integer.")
        if index < 0:
            raise ValueError("ServerStreamEvent index must not be negative.")
        if not isinstance(text, str):
            raise TypeError("ServerStreamEvent text must be a string.")
        if finish_reason is not None and not isinstance(finish_reason, str):
            raise TypeError("ServerStreamEvent finish_reason must be a string or None.")
        if response_id is not None and not isinstance(response_id, str):
            raise TypeError("ServerStreamEvent response_id must be a string or None.")
        if model is not None and not isinstance(model, str):
            raise TypeError("ServerStreamEvent model must be a string or None.")
        if type(done) is not bool:
            raise TypeError("ServerStreamEvent done must be a bool.")
        # The terminal marker is not a token. Text and a finish reason would
        # make a caller treat the end of the stream as another delta.
        if done and (text != "" or finish_reason is not None):
            raise ValueError(
                "A done ServerStreamEvent must not carry text or a finish reason."
            )

    @classmethod
    def finished(cls) -> ServerStreamEvent:
        """Return the terminal event that carries no model text."""
        # One shared shape lets every stream end with the same observation,
        # whether the service sent ``[DONE]`` or only closed the body.
        return cls(0, "", done=True)
