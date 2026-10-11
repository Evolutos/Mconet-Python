"""Classification tests for received HTTP status codes."""

from collections.abc import Callable
from typing import cast

from mconet.core.domain import ModelInteractionError, OpenIdentifier
from mconet.core.spi import TransportOutcome
from mconet.transport.http_system import HttpStatusOutcome, map_http_status


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> BaseException:
    """Require an action to raise the expected exception and message fragment."""
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return error
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_map_http_status_classifies_success_and_preserves_the_code() -> None:
    """Verify every 2xx result stays success and keeps its status."""
    for status_code in (200, 201, 204, 299):
        mapped = map_http_status(status_code)
        assert mapped == HttpStatusOutcome(
            TransportOutcome(OpenIdentifier("success")),
            status_code,
        )
        assert mapped.status_code == status_code


def test_map_http_status_classifies_other_received_codes_as_service_errors() -> None:
    """Verify 1xx, 3xx, 4xx, and 5xx retain the status as service errors."""
    for status_code in (100, 301, 302, 400, 404, 429, 500, 599):
        mapped = map_http_status(status_code)
        assert mapped.outcome == TransportOutcome(OpenIdentifier("service_error"))
        assert mapped.status_code == status_code
        assert str(mapped.outcome) == "service_error"


def test_map_http_status_rejects_a_code_outside_the_received_range() -> None:
    """Verify codes that are not HTTP response statuses fail closed."""
    for status_code in (0, 99, 600, -1):
        error = _assert_raises(
            ModelInteractionError,
            lambda status_code=status_code: map_http_status(status_code),
            "not a received response status",
        )
        assert isinstance(error, ModelInteractionError)
        assert error.code == "invalid_http_status"
        assert error.category.id == OpenIdentifier("invalid_request")
        assert error.phase.id == OpenIdentifier("transport")
        assert error.status_code is None
        assert str(status_code) not in error.message


def test_map_http_status_rejects_a_boolean() -> None:
    """Verify True is not treated as HTTP 1."""
    _assert_raises(
        TypeError,
        lambda: map_http_status(cast(int, True)),
        "status_code must be an integer",
    )
