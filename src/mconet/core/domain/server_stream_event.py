"""One event yielded by a server-stream model interaction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from mconet.core.domain.tool_call_element import ToolCallElement


@dataclass(frozen=True, slots=True)
class ServerStreamEvent:
    """Carry one incremental server-stream observation.

    A content event reports the choice index, the text delta, any tool-call
    deltas, and any finish reason the service attached to that same chunk. A
    terminal event has ``done`` set and empty text; it marks the end of the
    stream and does not itself contain a model token. The value stores no
    socket, buffer, or credential.
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

    tool_calls: tuple[ToolCallElement, ...] | None = None
    """Tool calls assembled for this choice so far, or ``None`` when it has none.

    Argument fragments that share a call index are concatenated before the
    event is built. A call appears once its id, type, and function name have
    arrived. Later events for the same choice replace the tuple with the
    updated calls.
    """

    done: bool = False
    """True only for the terminal event that ends the stream."""

    def __post_init__(self) -> None:
        """Require the event fields to use their declared storage types."""
        index = cast(object, self.index)
        text = cast(object, self.text)
        finish_reason = cast(object, self.finish_reason)
        response_id = cast(object, self.response_id)
        model = cast(object, self.model)
        tool_calls = cast(object, self.tool_calls)
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
        if tool_calls is not None:
            # None means this choice has no assembled call yet. An empty tuple
            # would look like a present member with nothing to observe.
            if not isinstance(tool_calls, tuple) or not tool_calls:
                raise TypeError(
                    "ServerStreamEvent tool_calls must be a non-empty tuple or None."
                )
            for item in cast(tuple[object, ...], tool_calls):
                # Each item is one assembled call. A raw delta object would
                # skip the string checks ToolCallElement already applied.
                if not isinstance(item, ToolCallElement):
                    raise TypeError(
                        "ServerStreamEvent tool_calls must contain ToolCallElement "
                        "values."
                    )
        if type(done) is not bool:
            raise TypeError("ServerStreamEvent done must be a bool.")
        # The terminal marker is not a token. Text, a finish reason, or a tool
        # call would make a caller treat the end of the stream as another delta.
        if done and (text != "" or finish_reason is not None or tool_calls is not None):
            raise ValueError(
                "A done ServerStreamEvent must not carry text, a finish reason, "
                "or tool calls."
            )

    @classmethod
    def finished(cls) -> ServerStreamEvent:
        """Return the terminal event that carries no model text."""
        # One shared shape lets every stream end with the same observation,
        # whether the service sent ``[DONE]`` or only closed the body.
        return cls(0, "", done=True)
