"""Ordered HTTP query encoding."""

from __future__ import annotations

from typing import cast
from urllib.parse import urlencode

from mconet.core.domain.error_category import ErrorCategory
from mconet.core.domain.interaction_phase import InteractionPhase
from mconet.core.domain.model_interaction_error import ModelInteractionError
from mconet.core.domain.open_identifier import OpenIdentifier
from mconet.core.domain.query_parameter import QueryParameter
from mconet.core.domain.query_parameters import QueryParameters

_QUERY_ENCODING = "utf-8"
_INVALID_REQUEST_CATEGORY = ErrorCategory(OpenIdentifier("invalid_request"))
_TRANSPORT_PHASE = InteractionPhase(OpenIdentifier("transport"))
_INVALID_HTTP_QUERY_CODE = "invalid_http_query"
_INVALID_HTTP_QUERY_MESSAGE = "HTTP query could not be encoded."


def map_http_query(query: QueryParameters) -> str:
    """Encode ordered query parameters without merging repeated names.

    The result uses standard-library query encoding: UTF-8 percent-encoding,
    with a space represented as ``+``. An empty collection encodes as an empty
    string and does not add a ``?``. The function does not sort names, drop
    repeated names, read a URL or headers, or open a connection.

    Args:
        query: Ordered parameters whose text has not yet been URL-encoded.

    Returns:
        The encoded query string, without a leading ``?``.

    Raises:
        TypeError: If ``query`` or its stored parameters have an invalid shape.
        ModelInteractionError: If a parameter cannot be encoded as UTF-8. The
            stable code is ``invalid_http_query``. Parameter text is omitted.
    """
    candidate = cast(object, query)
    if not isinstance(candidate, QueryParameters):
        raise TypeError("query must be QueryParameters.")

    values = cast(object, candidate.values)
    # Recheck tuple storage so a corrupted collection cannot change order while
    # the pairs are copied into the encoder.
    if not isinstance(values, tuple):
        raise TypeError("QueryParameters values must be a tuple.")

    pairs: list[tuple[str, str]] = []
    for parameter in cast(tuple[object, ...], values):
        if not isinstance(parameter, QueryParameter):
            raise TypeError(
                "QueryParameters values must contain QueryParameter values."
            )
        name = cast(object, parameter.name)
        value = cast(object, parameter.value)
        # Encode the stored text only. A non-string would be coerced by the
        # encoder into a different token than the caller supplied.
        if not isinstance(name, str) or not isinstance(value, str):
            raise TypeError("QueryParameter name and value must be strings.")
        pairs.append((name, value))

    # An empty collection is not a lone question mark. urlencode would also
    # return an empty string, but skipping it keeps the no-query result local.
    if not pairs:
        return ""

    try:
        # A sequence of pairs keeps repeated names and their original order.
        # A mapping would collapse those names, so it is not used.
        encoded = urlencode(pairs, encoding=_QUERY_ENCODING)
    except UnicodeEncodeError:
        raise _invalid_http_query_error() from None
    return encoded


def _invalid_http_query_error() -> ModelInteractionError:
    """Create the content-safe failure for one unencodable query.

    Returns:
        A transport error that does not include parameter text.
    """
    # Parameter text is omitted because a value can carry a credential that
    # must not enter errors, diagnostics, or logs.
    return ModelInteractionError(
        category=_INVALID_REQUEST_CATEGORY,
        phase=_TRANSPORT_PHASE,
        code=_INVALID_HTTP_QUERY_CODE,
        message=_INVALID_HTTP_QUERY_MESSAGE,
    )
