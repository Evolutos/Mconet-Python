"""Order and encoding tests for HTTP query mapping."""

from collections.abc import Callable
from typing import cast

from mconet.core.domain import (
    ModelInteractionError,
    OpenIdentifier,
    QueryParameter,
    QueryParameters,
)
from mconet.transport.http_system import map_http_query

_SECRET = "query-secret-value"


def _parameters(*pairs: tuple[str, str]) -> QueryParameters:
    """Build ordered parameters without encoding their text."""
    return QueryParameters(tuple(QueryParameter(name, value) for name, value in pairs))


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


def test_map_http_query_preserves_repeated_names_and_order() -> None:
    """Verify repeated names stay separate and unsorted."""
    query = _parameters(("b", "2"), ("a", "1"), ("a", "3"))

    # Dict encoding would collapse the two ``a`` values or sort the names.
    assert map_http_query(query) == "b=2&a=1&a=3"
    assert query.values == (
        QueryParameter("b", "2"),
        QueryParameter("a", "1"),
        QueryParameter("a", "3"),
    )


def test_map_http_query_encodes_space_reserved_characters_and_unicode() -> None:
    """Verify raw parameter text is encoded once."""
    assert map_http_query(_parameters(("q", "my model"))) == "q=my+model"
    assert map_http_query(_parameters(("q", "a&b=c"))) == "q=a%26b%3Dc"
    assert map_http_query(_parameters(("q", "100%"))) == "q=100%25"
    assert map_http_query(_parameters(("n", "你好"))) == "n=%E4%BD%A0%E5%A5%BD"
    assert map_http_query(_parameters(("q", ""))) == "q="
    assert map_http_query(_parameters(("", "x"))) == "=x"


def test_map_http_query_encodes_controls_and_returns_empty_for_no_parameters() -> None:
    """Verify controls cannot split the query and absence stays empty."""
    encoded = map_http_query(_parameters(("a", "b\r\nX-Injected: 1")))

    assert encoded == "a=b%0D%0AX-Injected%3A+1"
    assert "\r" not in encoded
    assert "\n" not in encoded
    assert map_http_query(QueryParameters()) == ""


def test_map_http_query_omits_unencodable_parameter_text() -> None:
    """Verify a surrogate value cannot be recovered from the error."""
    error = _assert_raises(
        ModelInteractionError,
        lambda: map_http_query(_parameters(("token", f"{_SECRET}\ud800"))),
        "HTTP query could not be encoded",
    )

    assert isinstance(error, ModelInteractionError)
    assert error.category.id == OpenIdentifier("invalid_request")
    assert error.phase.id == OpenIdentifier("transport")
    assert error.code == "invalid_http_query"
    assert error.message == "HTTP query could not be encoded."
    assert _SECRET not in error.message
    assert _SECRET not in str(error)
    assert error.cause is None


def test_map_http_query_rejects_non_query_parameters() -> None:
    """Verify arbitrary values are not encoded as a query string."""
    _assert_raises(
        TypeError,
        lambda: map_http_query(cast(QueryParameters, (("a", "1"),))),
        "query must be QueryParameters",
    )
