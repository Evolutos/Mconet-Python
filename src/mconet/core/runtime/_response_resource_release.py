"""Release of one response body and connection after a later stage."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar, cast

from mconet.core.domain.bytes_value import Bytes

_T = TypeVar("_T")


class ResponseResources:
    """Own one response body and one connection closer until release.

    Release drops the body reference and closes the connection once. A second
    release does not close the connection again. Decode, parse, and monitor
    stages do not own this cleanup; they run while the resources are still
    held, and the scheduler releases them afterward.
    """

    __slots__ = ("_body", "_release_connection", "_released")

    def __init__(
        self,
        body: Bytes,
        release_connection: Callable[[], None],
    ) -> None:
        """Store the body and the connection closer.

        Args:
            body: Response bytes held until release.
            release_connection: Closer invoked once by ``release``.

        Raises:
            TypeError: If an argument has an invalid type.
        """
        body_value = cast(object, body)
        closer_value = cast(object, release_connection)
        if not isinstance(body_value, bytes):
            raise TypeError("body must be bytes.")
        if not isinstance(closer_value, Callable):
            raise TypeError("release_connection must be callable.")
        self._body: Bytes | None = cast(Bytes, body_value)
        self._release_connection = cast(Callable[[], None], closer_value)
        self._released = False

    @property
    def body(self) -> Bytes | None:
        """Return the held body, or None after release."""
        return self._body

    @property
    def released(self) -> bool:
        """Return whether release has already run."""
        return self._released

    def release(self) -> None:
        """Drop the body and close the connection once."""
        if self._released:
            return
        # Mark release before closing so a closer failure cannot retry the
        # connection or resurrect the body on a later call.
        self._released = True
        self._body = None
        self._release_connection()


def release_response_after(
    resources: ResponseResources,
    operation: Callable[[], _T],
) -> _T:
    """Run one later stage and always release the response resources.

    The stage may be decoding, parsing, or monitoring. Its exception still
    propagates, and the body and connection are released either way.

    Args:
        resources: Body and connection held for this response.
        operation: The stage that runs before release.

    Returns:
        The value returned by that single stage call.

    Raises:
        TypeError: If an argument has an invalid type.
        Exception: The exception raised by the stage, after release.
    """
    resources_value = cast(object, resources)
    operation_value = cast(object, operation)
    if not isinstance(resources_value, ResponseResources):
        raise TypeError("resources must be a ResponseResources.")
    if not isinstance(operation_value, Callable):
        raise TypeError("operation must be callable.")
    checked = cast(Callable[[], _T], operation_value)
    try:
        return checked()
    finally:
        resources_value.release()
