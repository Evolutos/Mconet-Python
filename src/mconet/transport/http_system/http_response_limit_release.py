"""Release the HTTP connection when a response body exceeds its limit."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import cast

from mconet.core.domain.bytes_value import Bytes
from mconet.core.domain.model_interaction_error import ModelInteractionError
from mconet.transport.http_system.http_response_body import (
    read_bounded_http_response_body,
)

_TOO_LARGE_CODE = "response_body_too_large"


def read_bounded_http_response_releasing_connection(
    chunks: Iterable[bytes],
    max_byte_length: int,
    release: Callable[[], None],
) -> Bytes:
    """Read a bounded body and release the connection when the limit is hit.

    The size check stops pulling chunks before this function calls
    ``release``. ``release`` aborts the underlying read and drops the
    connection. It runs once, and only for ``response_body_too_large``. A body
    that fits, or a limit that cannot be enforced, leaves the connection to
    the caller. A failure inside ``release`` does not replace the size error;
    it is retained as that error's cause.

    Args:
        chunks: Ordered response chunks.
        max_byte_length: Maximum accepted total as a positive safe integer.
        release: Callback that aborts the read and releases the connection.

    Returns:
        The accepted body when every chunk fits.

    Raises:
        TypeError: If ``release`` is not callable.
        ModelInteractionError: If the limit is unusable, or the body would
            exceed it. The size failure still uses ``response_body_too_large``.
    """
    cancel = cast(object, release)
    if not callable(cancel):
        raise TypeError("release must be callable.")

    try:
        return read_bounded_http_response_body(chunks, max_byte_length)
    except ModelInteractionError as error:
        if error.code != _TOO_LARGE_CODE:
            raise
        _release_connection(release, error)
        raise


def _release_connection(
    release: Callable[[], None],
    error: ModelInteractionError,
) -> None:
    """Run the connection release once, keeping the size error primary."""
    try:
        release()
    except Exception as release_error:
        # The caller still observes the size limit. The release failure is
        # attached rather than turned into a different code.
        raise ModelInteractionError(
            category=error.category,
            phase=error.phase,
            code=error.code,
            message=error.message,
            cause=release_error,
        ) from release_error
