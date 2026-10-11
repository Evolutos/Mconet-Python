"""Tests that an oversized HTTP response releases its connection."""

from collections.abc import Callable, Iterator
from typing import cast

from mconet.core.domain import ModelInteractionError, OpenIdentifier
from mconet.transport.http_system import (
    read_bounded_http_response_releasing_connection,
)

_MAXIMUM_BODY_BYTES = 4
_SECRET = "connection-secret.example"


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


def test_oversized_http_response_releases_the_connection_once() -> None:
    """Verify the size error stops the read and releases the connection."""
    reads = 0
    releases = 0

    def chunks() -> Iterator[bytes]:
        nonlocal reads
        reads += 1
        yield b"\x01\x02"
        reads += 1
        yield b"\x03\x04\x05"
        reads += 1
        raise AssertionError("reader pulled past the failing chunk")

    def release() -> None:
        nonlocal releases
        releases += 1

    error = _assert_raises(
        ModelInteractionError,
        lambda: read_bounded_http_response_releasing_connection(
            chunks(),
            _MAXIMUM_BODY_BYTES,
            release,
        ),
        "exceeds its byte limit",
    )

    interaction_error = cast(ModelInteractionError, error)
    assert reads == 2
    assert releases == 1
    assert interaction_error.code == "response_body_too_large"
    assert interaction_error.category.id == OpenIdentifier("network")
    assert interaction_error.phase.id == OpenIdentifier("transport")
    assert interaction_error.cause is None


def test_fitting_http_response_does_not_release_the_connection() -> None:
    """Verify a body inside the limit leaves connection ownership unchanged."""
    releases = 0

    def release() -> None:
        nonlocal releases
        releases += 1

    body = read_bounded_http_response_releasing_connection(
        (b"\x01\x02",),
        _MAXIMUM_BODY_BYTES,
        release,
    )

    assert body == b"\x01\x02"
    assert releases == 0


def test_unusable_http_response_limit_does_not_release_the_connection() -> None:
    """Verify a configuration failure is not reported as a size-limit cancel."""
    releases = 0

    def release() -> None:
        nonlocal releases
        releases += 1

    error = _assert_raises(
        ModelInteractionError,
        lambda: read_bounded_http_response_releasing_connection((), 0, release),
        "positive safe integer",
    )

    assert releases == 0
    assert cast(ModelInteractionError, error).code == "invalid_component_configuration"


def test_failed_connection_release_keeps_the_size_error() -> None:
    """Verify a release failure does not replace the size code or leak its text."""

    def release() -> None:
        raise ConnectionError(f"close failed for {_SECRET}")

    error = _assert_raises(
        ModelInteractionError,
        lambda: read_bounded_http_response_releasing_connection(
            (b"\x01\x02\x03\x04\x05",),
            _MAXIMUM_BODY_BYTES,
            release,
        ),
        "exceeds its byte limit",
    )

    interaction_error = cast(ModelInteractionError, error)
    assert interaction_error.code == "response_body_too_large"
    assert isinstance(interaction_error.cause, ConnectionError)
    assert _SECRET not in str(interaction_error)


def test_http_response_release_must_be_callable_before_reading() -> None:
    """Verify a missing release callback does not pull response bytes."""
    reads = 0

    def chunks() -> Iterator[bytes]:
        nonlocal reads
        reads += 1
        yield b"\x01"

    _assert_raises(
        TypeError,
        lambda: read_bounded_http_response_releasing_connection(
            chunks(),
            _MAXIMUM_BODY_BYTES,
            cast(Callable[[], None], None),
        ),
        "release must be callable",
    )
    assert reads == 0
