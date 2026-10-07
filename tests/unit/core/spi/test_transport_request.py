"""Composition tests for immutable transport requests."""

from collections.abc import Callable
from dataclasses import FrozenInstanceError, fields
from typing import cast

from mconet.core.domain import (
    Bytes,
    HeaderField,
    Headers,
    MediaType,
    QueryParameter,
    QueryParameters,
    UriValue,
)
from mconet.core.spi import TransportBody, TransportRequest


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    try:
        action()
    except exception_type as error:
        # Match a stable boundary fragment so an unrelated fixture failure
        # cannot make a negative request-composition test pass accidentally.
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def _request() -> TransportRequest:
    """Build a representative request containing repeated ordered values."""
    # Use repeated names with distinct spelling and values so every composition
    # assertion can detect normalization, merging, or reordering.
    headers = Headers(
        (
            HeaderField("X-Trace", "first"),
            HeaderField("x-trace", "second"),
        )
    )
    query = QueryParameters(
        (
            QueryParameter("tag", "one"),
            QueryParameter("tag", "two"),
        )
    )
    return TransportRequest(
        "VENDOR-CALL",
        UriValue("https://example.test/models/run", True),
        headers,
        query,
        TransportBody(Bytes(b'{"prompt":"hello"}'), MediaType("application", "json")),
    )


def test_transport_request_preserves_all_composed_values() -> None:
    """Verify every transport-ready value remains exact and ordered."""
    request = _request()

    # Extension methods remain available, and the already structured URL and
    # body pass through without protocol-specific parsing or normalization.
    assert request.method == "VENDOR-CALL"
    assert request.url.value == "https://example.test/models/run"
    assert request.url.is_absolute is True
    assert request.body.bytes == b'{"prompt":"hello"}'
    assert str(request.body.media_type) == "application/json"

    # Repeated headers and query parameters remain separate and retain caller
    # order for the selected transport to serialize according to its protocol.
    assert request.headers.values == (
        HeaderField("X-Trace", "first"),
        HeaderField("x-trace", "second"),
    )
    assert request.query.values == (
        QueryParameter("tag", "one"),
        QueryParameter("tag", "two"),
    )


def test_transport_request_retains_component_identity() -> None:
    """Verify construction does not replace established immutable values."""
    url = UriValue("/models/run", False)
    headers = Headers()
    query = QueryParameters()
    body = TransportBody(Bytes(b""), MediaType("application", "octet-stream"))

    request = TransportRequest("POST", url, headers, query, body)

    # Identity preservation proves the request is a composition boundary rather
    # than an implicit URL validator, collection copier, or body encoder.
    assert request.url is url
    assert request.headers is headers
    assert request.query is query
    assert request.body is body


def test_transport_request_has_immutable_value_semantics() -> None:
    """Verify equality, hashing, and frozen fields cover the full request."""
    first = _request()
    same = _request()
    different = TransportRequest(
        "POST", first.url, first.headers, first.query, first.body
    )

    # Every composed fact participates in value identity, and the frozen
    # snapshot cannot change once authorization or dispatch observes it.
    assert first == same
    assert hash(first) == hash(same)
    assert first != different
    _assert_raises(
        FrozenInstanceError,
        lambda: first.__setattr__("method", "DELETE"),
        "cannot assign to field",
    )


def test_transport_request_exposes_only_dispatch_input_fields() -> None:
    """Verify unrelated response and runtime context data stay outside requests."""
    request = _request()

    # The exact surface prevents this value from absorbing endpoint resolution,
    # response metadata, authorization state, or interaction context ownership.
    assert tuple(field.name for field in fields(TransportRequest)) == (
        "method",
        "url",
        "headers",
        "query",
        "body",
    )
    assert not hasattr(request, "endpoint")
    assert not hasattr(request, "metadata")
    assert not hasattr(request, "authorization")
    assert not hasattr(request, "context")


def test_transport_request_rejects_invalid_method_and_url_types() -> None:
    """Verify primitive and nominal destination boundaries reject substitutes."""
    request = _request()

    # Neither a numeric method nor a raw URL string receives an implicit
    # conversion because doing so would discard explicit request-mapping facts.
    _assert_raises(
        TypeError,
        lambda: TransportRequest(
            cast(str, 1),
            request.url,
            request.headers,
            request.query,
            request.body,
        ),
        "method must be a string",
    )
    _assert_raises(
        TypeError,
        lambda: TransportRequest(
            request.method,
            cast(UriValue, "https://example.test"),
            request.headers,
            request.query,
            request.body,
        ),
        "url must be a UriValue",
    )


def test_transport_request_rejects_unstructured_collections_and_body() -> None:
    """Verify dynamic callers cannot bypass immutable component contracts."""
    request = _request()

    # Validate every remaining nominal boundary independently so a mutable dict,
    # tuple, or raw byte sequence cannot leak into the frozen request snapshot.
    _assert_raises(
        TypeError,
        lambda: TransportRequest(
            request.method,
            request.url,
            cast(Headers, ()),
            request.query,
            request.body,
        ),
        "headers must be Headers",
    )
    _assert_raises(
        TypeError,
        lambda: TransportRequest(
            request.method,
            request.url,
            request.headers,
            cast(QueryParameters, ()),
            request.body,
        ),
        "query must be QueryParameters",
    )
    _assert_raises(
        TypeError,
        lambda: TransportRequest(
            request.method,
            request.url,
            request.headers,
            request.query,
            cast(TransportBody, b"payload"),
        ),
        "body must be a TransportBody",
    )
