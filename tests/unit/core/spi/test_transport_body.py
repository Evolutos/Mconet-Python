"""Complete-byte representation tests for the current transport body."""

from collections.abc import Callable
from dataclasses import FrozenInstanceError, fields
from typing import cast

from mconet.core.domain import Bytes, MediaType
from mconet.core.spi import TransportBody


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    try:
        action()
    except exception_type as error:
        # Check stable body diagnostics so unrelated fixture failures cannot make
        # a negative storage test appear successful.
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_transport_body_preserves_complete_bytes_and_media_type() -> None:
    """Verify encoded octets and representation metadata remain exact."""
    content = Bytes(bytes((0, 127, 255)))
    media_type = MediaType(
        "application",
        "vnd.vendor+json",
        (("charset", "utf-8"),),
    )

    body = TransportBody(content, media_type)

    # Both immutable values retain identity; body construction never re-encodes
    # payload data or reparses the already structured media type.
    assert body.bytes is content
    assert body.bytes == b"\x00\x7f\xff"
    assert body.media_type is media_type


def test_transport_body_supports_explicit_empty_bytes() -> None:
    """Verify a zero-length encoded payload remains a valid Bytes body."""
    body = TransportBody(Bytes(b""), MediaType("application", "json"))

    # Empty bytes are a present encoded body, not an implicit EmptyBody variant
    # or a missing nullable field.
    assert body.bytes == b""
    assert len(body.bytes) == 0
    assert str(body.media_type) == "application/json"


def test_transport_body_has_immutable_value_semantics() -> None:
    """Verify equality, hashing, and frozen fields include both body facts."""
    first = TransportBody(Bytes(b"payload"), MediaType("application", "json"))
    same = TransportBody(Bytes(b"payload"), MediaType("application", "json"))
    different_media = TransportBody(
        Bytes(b"payload"), MediaType("application", "octet-stream")
    )

    # Content and representation jointly define the complete current body;
    # neither can be replaced after authorization begins.
    assert first == same
    assert hash(first) == hash(same)
    assert first != different_media
    _assert_raises(
        FrozenInstanceError,
        lambda: first.__setattr__("bytes", Bytes(b"changed")),
        "cannot assign to field",
    )


def test_transport_body_exposes_only_the_complete_bytes_variant() -> None:
    """Verify unsupported body representations have no constructible surface."""
    body = TransportBody(Bytes(b"payload"), MediaType("application", "json"))

    # The exact field surface prevents callers from constructing inert empty,
    # stream, or multipart placeholders before those semantics are implemented.
    assert tuple(field.name for field in fields(TransportBody)) == (
        "bytes",
        "media_type",
    )
    assert not hasattr(body, "source")
    assert not hasattr(body, "parts")
    assert not hasattr(body, "open_stream")
    assert not hasattr(body, "repeatability")


def test_transport_body_rejects_mutable_and_non_byte_payloads() -> None:
    """Verify the supported body cannot retain mutable or textual content."""
    media_type = MediaType("application", "octet-stream")

    # Dynamic callers must explicitly snapshot mutable binary inputs to bytes;
    # implicit conversion could hide ownership and later mutation mistakes.
    for value in (bytearray(b"mutable"), memoryview(b"view"), "text", None):
        _assert_raises(
            TypeError,
            lambda value=value: TransportBody(cast(Bytes, value), media_type),
            "bytes must be a Bytes value",
        )


def test_transport_body_requires_structured_media_type() -> None:
    """Verify callers cannot pass raw, missing, or unrelated media metadata."""
    # Media type parsing stays an explicit upstream step. This value neither
    # accepts a raw header string nor invents a default from the encoded bytes.
    for value in ("application/json", None, object()):
        _assert_raises(
            TypeError,
            lambda value=value: TransportBody(
                Bytes(b"payload"), cast(MediaType, value)
            ),
            "media_type must be a MediaType",
        )
