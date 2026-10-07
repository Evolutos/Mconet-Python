"""Response-fact tests for immutable transport metadata."""

import math
import operator
from collections.abc import Callable, MutableMapping
from dataclasses import FrozenInstanceError, fields
from typing import cast

from mconet.core.domain import (
    Extensions,
    HeaderField,
    Headers,
    JsonValue,
    MediaType,
    OpenIdentifier,
)
from mconet.core.spi import TransportOutcome, TransportResponseMetadata


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    try:
        action()
    except exception_type as error:
        # Stable field-specific diagnostics ensure unrelated fixture errors do
        # not make a negative metadata test appear successful.
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def _outcome(value: str = "success") -> TransportOutcome:
    """Build one normalized transport outcome for metadata fixtures."""
    # Construct through the public open identifier path so fixture values obey
    # the same portability rules as production transport outcomes.
    return TransportOutcome(OpenIdentifier(value))


def test_transport_response_metadata_preserves_complete_response_facts() -> None:
    """Verify every normalized and native response fact remains exact."""
    outcome = _outcome("service_error")
    headers = Headers(
        (
            HeaderField("Set-Cookie", "first=1"),
            HeaderField("set-cookie", "second=2"),
        )
    )
    trailers = Headers((HeaderField("X-Checksum", "abc123"),))
    media_type = MediaType("application", "problem+json", (("charset", "utf-8"),))

    metadata = TransportResponseMetadata(
        outcome,
        headers,
        status_code=429,
        protocol_status_code="RESOURCE_EXHAUSTED",
        trailers=trailers,
        media_type=media_type,
        request_id="request-7",
        extensions={"vendor.retry_class": "quota", "vendor.attempt": 2},
    )

    # Normalized classification and every structured value retain identity;
    # construction does not derive outcome from either native status channel.
    assert metadata.outcome is outcome
    assert metadata.headers is headers
    assert metadata.trailers is trailers
    assert metadata.media_type is media_type
    assert metadata.status_code == 429
    assert metadata.protocol_status_code == "RESOURCE_EXHAUSTED"
    assert metadata.request_id == "request-7"
    assert metadata.extensions == {
        "vendor.retry_class": "quota",
        "vendor.attempt": 2,
    }


def test_transport_response_metadata_preserves_absent_optional_facts() -> None:
    """Verify missing response observations remain absent without inference."""
    metadata = TransportResponseMetadata(_outcome(), Headers())

    # None means the transport did not report the corresponding fact. Empty
    # primary Headers is an explicit collection, not missing metadata.
    assert metadata.status_code is None
    assert metadata.protocol_status_code is None
    assert metadata.trailers is None
    assert metadata.media_type is None
    assert metadata.request_id is None
    assert metadata.headers.values == ()
    assert metadata.extensions == {}


def test_transport_response_metadata_does_not_infer_outcome_from_status() -> None:
    """Verify normalized outcome remains independent from native status values."""
    metadata = TransportResponseMetadata(
        _outcome("success"),
        Headers(),
        status_code=503,
        protocol_status_code="CUSTOM_FAILURE",
    )

    # A deliberately inconsistent fixture remains exact because only a concrete
    # transport owns HTTP or RPC classification rules; Runtime must not guess.
    assert str(metadata.outcome) == "success"
    assert metadata.status_code == 503
    assert metadata.protocol_status_code == "CUSTOM_FAILURE"


def test_transport_response_metadata_freezes_extension_membership() -> None:
    """Verify portable extensions are validated and detached from source changes."""
    source: dict[str, JsonValue] = {
        "vendor.trace": {"sampled": True},
        "vendor.latency_ms": 12.5,
    }
    metadata = TransportResponseMetadata(_outcome(), Headers(), extensions=source)
    source["later"] = "ignored"

    # The outer snapshot rejects mutation and ignores later source membership;
    # exact nested portable JSON remains available to transport-aware consumers.
    assert metadata.extensions == {
        "vendor.trace": {"sampled": True},
        "vendor.latency_ms": 12.5,
    }
    assert "later" not in metadata.extensions
    _assert_raises(
        TypeError,
        lambda: operator.setitem(
            cast(MutableMapping[str, JsonValue], metadata.extensions),
            "vendor.new",
            1,
        ),
        "does not support item assignment",
    )


def test_transport_response_metadata_has_complete_frozen_value_semantics() -> None:
    """Verify equality, field ownership, and frozen replacement behavior."""
    first = TransportResponseMetadata(_outcome(), Headers(), status_code=204)
    same = TransportResponseMetadata(_outcome(), Headers(), status_code=204)
    different = TransportResponseMetadata(_outcome(), Headers(), status_code=200)

    # Every declared response fact participates in equality, while frozen slots
    # prevent a consumer from replacing classification after decoder dispatch.
    assert first == same
    assert first != different
    assert tuple(field.name for field in fields(TransportResponseMetadata)) == (
        "outcome",
        "headers",
        "status_code",
        "protocol_status_code",
        "trailers",
        "media_type",
        "request_id",
        "extensions",
    )
    _assert_raises(
        FrozenInstanceError,
        lambda: first.__setattr__("status_code", 500),
        "cannot assign to field",
    )


def test_transport_response_metadata_rejects_invalid_primary_types() -> None:
    """Verify outcome, header, and numeric status boundaries are nominal and exact."""
    # Test each required or numeric field independently so strings, tuples, and
    # bool-as-int values cannot cross the transport SPI through dynamic calls.
    _assert_raises(
        TypeError,
        lambda: TransportResponseMetadata(cast(TransportOutcome, "success"), Headers()),
        "outcome must be a TransportOutcome",
    )
    _assert_raises(
        TypeError,
        lambda: TransportResponseMetadata(_outcome(), cast(Headers, ())),
        "headers must be Headers",
    )
    for value in (True, 200.0, "200", object()):
        _assert_raises(
            TypeError,
            lambda value=value: TransportResponseMetadata(
                _outcome(), Headers(), status_code=cast(int, value)
            ),
            "status_code must be an integer or None",
        )


def test_transport_response_metadata_rejects_invalid_optional_types() -> None:
    """Verify optional response facts cannot use raw or unrelated substitutes."""
    # Each optional nominal value retains None as its only absence representation;
    # no string parsing or collection conversion occurs inside metadata storage.
    invalid_cases: tuple[tuple[str, Callable[[], TransportResponseMetadata]], ...] = (
        (
            "protocol_status_code must be a string or None",
            lambda: TransportResponseMetadata(
                _outcome(), Headers(), protocol_status_code=cast(str, 13)
            ),
        ),
        (
            "trailers must be Headers or None",
            lambda: TransportResponseMetadata(
                _outcome(), Headers(), trailers=cast(Headers, ())
            ),
        ),
        (
            "media_type must be a MediaType or None",
            lambda: TransportResponseMetadata(
                _outcome(), Headers(), media_type=cast(MediaType, "application/json")
            ),
        ),
        (
            "request_id must be a string or None",
            lambda: TransportResponseMetadata(
                _outcome(), Headers(), request_id=cast(str, 7)
            ),
        ),
    )
    for message, create_metadata in invalid_cases:
        _assert_raises(TypeError, create_metadata, message)


def test_transport_response_metadata_rejects_invalid_extensions() -> None:
    """Verify transport extensions obey mapping and portable JSON constraints."""
    cyclic: list[JsonValue] = []
    cyclic.append(cyclic)
    invalid_cases: tuple[tuple[Extensions, type[BaseException], str], ...] = (
        (cast(Extensions, []), TypeError, "extensions must be a mapping"),
        (cast(Extensions, {1: "bad"}), TypeError, "extensions keys must be strings"),
        (
            cast(Extensions, {"bad": object()}),
            TypeError,
            "structurally valid JsonValue",
        ),
        (
            {"bad": math.inf},
            ValueError,
            "floating-point value must be finite",
        ),
        (
            {"bad": cyclic},
            TypeError,
            "structurally valid JsonValue",
        ),
    )

    # Invalid outer shape, keys, recursive values, numbers, and cycles all fail
    # before any extension snapshot becomes publicly observable.
    for extensions, exception_type, message in invalid_cases:
        _assert_raises(
            exception_type,
            lambda extensions=extensions: TransportResponseMetadata(
                _outcome(), Headers(), extensions=extensions
            ),
            message,
        )
