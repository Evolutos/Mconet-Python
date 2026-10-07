"""Authorization-window and freezing tests for mutable transport requests."""

from collections.abc import Callable
from dataclasses import FrozenInstanceError
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
from mconet.core.spi import MutableTransportRequest, TransportBody, TransportRequest


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    try:
        action()
    except exception_type as error:
        # Match builder-owned diagnostics so a fixture or immutable child failure
        # cannot accidentally satisfy an authorization-window test.
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def _body(value: bytes = b"payload") -> TransportBody:
    """Build a complete encoded JSON body for request-window tests."""
    # Distinct byte values let replacement and snapshot assertions detect any
    # stale body reference without introducing encoder behavior into this test.
    return TransportBody(Bytes(value), MediaType("application", "json"))


def _request() -> MutableTransportRequest:
    """Build an open request with repeated ordered protocol values."""
    # Repeated values prove authorization replacements retain collection order
    # rather than converting Headers or QueryParameters into lossy mappings.
    return MutableTransportRequest(
        method="POST",
        url=UriValue("https://models.example.test/v1/run", True),
        headers=Headers(
            (
                HeaderField("X-Trace", "one"),
                HeaderField("x-trace", "two"),
            )
        ),
        query=QueryParameters(
            (
                QueryParameter("region", "east"),
                QueryParameter("region", "west"),
            )
        ),
        body=_body(),
    )


def test_mutable_transport_request_preserves_initial_values_and_identity() -> None:
    """Verify the open authorization window starts with exact request values."""
    url = UriValue("https://models.example.test/v1/run", True)
    headers = Headers((HeaderField("X-Feature", "enabled"),))
    query = QueryParameters((QueryParameter("region", "east"),))
    body = _body()

    request = MutableTransportRequest("VENDOR-CALL", url, headers, query, body)

    # The mutable builder composes established values without parsing the method,
    # rebuilding collections, encoding the body, or changing object identity.
    assert request.method == "VENDOR-CALL"
    assert request.url is url
    assert request.headers is headers
    assert request.query is query
    assert request.body is body
    assert request.is_frozen is False


def test_mutable_transport_request_replaces_only_authorization_window_values() -> None:
    """Verify URL, headers, query, and body can change before freezing."""
    request = _request()
    replacement_url = UriValue("https://signed.example.test/v1/run", True)
    replacement_headers = Headers(
        (
            HeaderField("Authorization", "redacted-test-value"),
            HeaderField("Cookie", "session=redacted-test-value"),
        )
    )
    replacement_query = QueryParameters(
        (
            QueryParameter("signature", "redacted-test-value"),
            QueryParameter("signature", "second-redacted-test-value"),
        )
    )
    replacement_body = _body(b"signed-payload")

    request.replace_url(replacement_url)
    request.replace_headers(replacement_headers)
    request.replace_query(replacement_query)
    request.replace_body(replacement_body)

    # Every authorized field uses whole-value replacement and retains identity;
    # the protocol method remains fixed because authorization may sign, not alter, it.
    assert request.method == "POST"
    assert request.url is replacement_url
    assert request.headers is replacement_headers
    assert request.query is replacement_query
    assert request.body is replacement_body
    assert request.is_frozen is False


def test_mutable_transport_request_freezes_one_immutable_snapshot() -> None:
    """Verify freezing closes authorization and returns one transport request."""
    request = _request()

    frozen = request.freeze()
    repeated = request.freeze()

    # The immutable request captures the final identities exactly. Idempotent
    # freezing cannot create two snapshots with potentially divergent ownership.
    assert isinstance(frozen, TransportRequest)
    assert repeated is frozen
    assert request.is_frozen is True
    assert frozen.method == request.method
    assert frozen.url is request.url
    assert frozen.headers is request.headers
    assert frozen.query is request.query
    assert frozen.body is request.body
    _assert_raises(
        FrozenInstanceError,
        lambda: frozen.__setattr__("method", "DELETE"),
        "cannot assign to field",
    )


def test_mutable_transport_request_rejects_every_replacement_after_freeze() -> None:
    """Verify no authorization field can change after snapshot publication."""
    request = _request()
    frozen = request.freeze()
    original_values = (request.url, request.headers, request.query, request.body)

    actions: tuple[Callable[[], object], ...] = (
        lambda: request.replace_url(UriValue("https://other.example.test", True)),
        lambda: request.replace_headers(Headers()),
        lambda: request.replace_query(QueryParameters()),
        lambda: request.replace_body(_body(b"other")),
    )

    # Every mutation path checks the lifecycle first and leaves both the builder
    # view and already published TransportRequest unchanged after rejection.
    for action in actions:
        _assert_raises(RuntimeError, action, "is frozen")
    assert (
        request.url,
        request.headers,
        request.query,
        request.body,
    ) == original_values
    assert frozen.url is original_values[0]
    assert frozen.headers is original_values[1]
    assert frozen.query is original_values[2]
    assert frozen.body is original_values[3]


def test_mutable_transport_request_blocks_direct_assignment_and_reopening() -> None:
    """Verify callers cannot bypass replacement validation or frozen state."""
    request = _request()

    # Public properties and private slots share one assignment guard, preventing
    # method replacement, unchecked field writes, and cached-snapshot removal.
    _assert_raises(
        AttributeError,
        lambda: request.__setattr__(("method"), "DELETE"),
        "through replace methods",
    )
    request.freeze()
    _assert_raises(
        AttributeError,
        lambda: request.__setattr__("_frozen_request", None),
        "through replace methods",
    )
    assert request.is_frozen is True


def test_mutable_transport_request_rejects_invalid_initial_values() -> None:
    """Verify construction enforces every immutable request value boundary."""
    request = _request()
    cases: tuple[tuple[str, Callable[[], object]], ...] = (
        (
            "method must be a string",
            lambda: MutableTransportRequest(
                cast(str, 1),
                request.url,
                request.headers,
                request.query,
                request.body,
            ),
        ),
        (
            "url must be a UriValue",
            lambda: MutableTransportRequest(
                request.method,
                cast(UriValue, "https://models.example.test"),
                request.headers,
                request.query,
                request.body,
            ),
        ),
        (
            "headers must be Headers",
            lambda: MutableTransportRequest(
                request.method,
                request.url,
                cast(Headers, ()),
                request.query,
                request.body,
            ),
        ),
        (
            "query must be QueryParameters",
            lambda: MutableTransportRequest(
                request.method,
                request.url,
                request.headers,
                cast(QueryParameters, ()),
                request.body,
            ),
        ),
        (
            "body must be a TransportBody",
            lambda: MutableTransportRequest(
                request.method,
                request.url,
                request.headers,
                request.query,
                cast(TransportBody, b"payload"),
            ),
        ),
    )

    # Exercise each boundary independently so dynamic callers receive the same
    # stable diagnostics before any partially initialized builder can escape.
    for message, action in cases:
        _assert_raises(TypeError, action, message)


def test_mutable_transport_request_rejects_invalid_replacements_atomically() -> None:
    """Verify malformed replacements fail without changing the open request."""
    request = _request()
    original_values = (request.url, request.headers, request.query, request.body)
    cases: tuple[tuple[str, Callable[[], object]], ...] = (
        (
            "url must be a UriValue",
            lambda: request.replace_url(cast(UriValue, "invalid")),
        ),
        (
            "headers must be Headers",
            lambda: request.replace_headers(cast(Headers, ())),
        ),
        (
            "query must be QueryParameters",
            lambda: request.replace_query(cast(QueryParameters, ())),
        ),
        (
            "body must be a TransportBody",
            lambda: request.replace_body(cast(TransportBody, b"invalid")),
        ),
    )

    # Validation precedes every internal write, so a failed handler operation
    # cannot leave a partially updated request for a later handler or transport.
    for message, action in cases:
        _assert_raises(TypeError, action, message)
    assert (
        request.url,
        request.headers,
        request.query,
        request.body,
    ) == original_values
