"""Composition and immutability tests for complete transport responses."""

from collections.abc import Callable
from dataclasses import FrozenInstanceError, fields
from typing import cast

from mconet.core.domain import Bytes, Headers, MediaType, OpenIdentifier
from mconet.core.spi import (
    TransportBody,
    TransportOutcome,
    TransportResponse,
    TransportResponseMetadata,
)


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    try:
        action()
    except exception_type as error:
        # Match the owned field diagnostic so an unrelated fixture exception
        # cannot make a negative response-boundary test pass accidentally.
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def _metadata(status_code: int | None = 200) -> TransportResponseMetadata:
    """Build one normalized response metadata fixture."""
    # Use only public immutable values so response tests exercise the same
    # construction path available to a concrete transport implementation.
    return TransportResponseMetadata(
        TransportOutcome(OpenIdentifier("success")),
        Headers(),
        status_code=status_code,
    )


def test_transport_response_preserves_metadata_and_complete_bytes() -> None:
    """Verify both transport output values remain exact and retain identity."""
    metadata = _metadata()
    body = Bytes(bytes((0, 127, 255)))

    response = TransportResponse(metadata, body)

    # Construction is a composition boundary: it neither copies response bytes
    # nor rebuilds metadata before Runtime inspects outcome and invokes a decoder.
    assert response.response_metadata is metadata
    assert response.body is body
    assert response.body == b"\x00\x7f\xff"


def test_transport_response_supports_explicit_empty_body() -> None:
    """Verify a zero-length received payload remains a valid complete body."""
    response = TransportResponse(_metadata(status_code=204), Bytes(b""))

    # Empty bytes is a present wire result, not a missing response, None value,
    # or request-side EmptyBody variant.
    assert response.body == b""
    assert len(response.body) == 0
    assert response.response_metadata.status_code == 204


def test_transport_response_has_frozen_value_semantics() -> None:
    """Verify equality and frozen fields cover metadata and body together."""
    first = TransportResponse(_metadata(), Bytes(b"payload"))
    same = TransportResponse(_metadata(), Bytes(b"payload"))
    different_body = TransportResponse(_metadata(), Bytes(b"other"))
    different_metadata = TransportResponse(_metadata(201), Bytes(b"payload"))

    # Metadata and bytes jointly determine response equality, while frozen slots
    # prevent changing the received payload after outcome-based dispatch begins.
    assert first == same
    assert first != different_body
    assert first != different_metadata
    _assert_raises(
        FrozenInstanceError,
        lambda: first.__setattr__("body", Bytes(b"changed")),
        "cannot assign to field",
    )


def test_transport_response_exposes_only_metadata_and_body() -> None:
    """Verify decoder, request, and control concerns remain outside responses."""
    response = TransportResponse(_metadata(), Bytes(b"payload"))

    # The exact two-field surface prevents this wire value from owning decoder
    # selection, request context, retry state, or a duplicate media type.
    assert tuple(field.name for field in fields(TransportResponse)) == (
        "response_metadata",
        "body",
    )
    assert not hasattr(response, "decoder")
    assert not hasattr(response, "request")
    assert not hasattr(response, "context")
    assert not hasattr(response, "media_type")


def test_transport_response_requires_response_metadata() -> None:
    """Verify native status and mapping substitutes cannot replace metadata."""
    # Common dynamic substitutes omit normalized outcome and structured response
    # facts, so none is coerced into a partial metadata value.
    for value in (200, {"status_code": 200}, None):
        _assert_raises(
            TypeError,
            lambda value=value: TransportResponse(
                cast(TransportResponseMetadata, value), Bytes(b"payload")
            ),
            "response_metadata must be a TransportResponseMetadata",
        )


def test_transport_response_rejects_mutable_and_wrapped_body_values() -> None:
    """Verify response payload storage accepts only complete immutable bytes."""
    metadata = _metadata()

    # A transport must snapshot mutable input explicitly. Text, None, and the
    # request-side body wrapper cannot masquerade as raw received response bytes.
    invalid_values = (
        bytearray(b"mutable"),
        memoryview(b"view"),
        "text",
        None,
        TransportBody(Bytes(b"request"), MediaType("application", "json")),
    )
    for value in invalid_values:
        _assert_raises(
            TypeError,
            lambda value=value: TransportResponse(metadata, cast(Bytes, value)),
            "body must be a Bytes value",
        )
