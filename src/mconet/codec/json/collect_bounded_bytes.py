"""Bounded collection of response body chunks."""

from __future__ import annotations

from collections.abc import Iterable
from typing import cast

from mconet.core.domain import (
    Bytes,
    ErrorCategory,
    InteractionPhase,
    ModelInteractionError,
    OpenIdentifier,
)

_MAX_SAFE_INTEGER = 2**53 - 1
_DECODING_PHASE = InteractionPhase(OpenIdentifier("decoding"))
_DESERIALIZATION_CATEGORY = ErrorCategory(OpenIdentifier("deserialization"))
_CONFIGURATION_CATEGORY = ErrorCategory(
    OpenIdentifier("invalid_component_configuration")
)
_TOO_LARGE_CODE = "response_body_too_large"
_DESERIALIZATION_CODE = "deserialization"
_CONFIGURATION_CODE = "invalid_component_configuration"
_TOO_LARGE_MESSAGE = "Response body exceeds its byte limit."
_CHUNK_MESSAGE = "Response body chunk must be bytes."
_LIMIT_MESSAGE = "Response body byte limit must be a positive safe integer."


def collect_bounded_bytes(chunks: Iterable[bytes], max_byte_length: int) -> Bytes:
    """Copy body chunks that fit inside a positive byte limit.

    The walk stops at the first chunk that would make the accepted total larger
    than ``max_byte_length``. That chunk is not copied, later chunks are not
    read, and the error does not retain any source bytes. An invalid limit
    fails before the first read. Bytes that fit an earlier chunk are discarded
    with the failed call rather than returned as a truncated body.

    The function does not decode text, parse JSON, or inspect a media type.

    Args:
        chunks: Ordered immutable byte chunks. Each chunk is measured by its
            own length.
        max_byte_length: Maximum accepted total as a positive safe integer.

    Returns:
        A new :data:`Bytes` value containing every accepted byte in source
        order.

    Raises:
        ModelInteractionError: If the limit is unusable, a chunk is not
            ``bytes``, or the body would exceed the limit.
    """
    # Reject the limit before touching the source so a bad configuration cannot
    # be reported as an oversized body or consume caller data.
    if not _is_positive_safe_integer(max_byte_length):
        raise _invalid_limit_error()

    accepted_chunks: list[bytes] = []
    accepted_byte_length = 0
    for raw_chunk in chunks:
        chunk = cast(object, raw_chunk)
        if not isinstance(chunk, bytes):
            # A mutable buffer or text cannot be measured as an immutable body
            # chunk. Fail without guessing a length or copying its contents.
            raise _invalid_chunk_error()

        # Compare against the remaining room so a huge chunk is not copied and
        # is not added into the accepted total.
        if len(chunk) > max_byte_length - accepted_byte_length:
            raise _response_body_too_large_error()

        accepted_chunks.append(chunk)
        accepted_byte_length += len(chunk)

    # Join only after every chunk fits. The result does not share the caller's
    # chunk objects, and a failed call never reaches this copy.
    return Bytes(b"".join(accepted_chunks))


def _is_positive_safe_integer(value: object) -> bool:
    """Return whether a limit is a positive integer inside the safe range."""
    # Exact int membership excludes bool. The upper bound matches the portable
    # integer range used by the rest of the JSON codec.
    return type(value) is int and 0 < value <= _MAX_SAFE_INTEGER


def _invalid_limit_error() -> ModelInteractionError:
    """Create the failure for a body limit that cannot be enforced."""
    # The diagnostic identifies the configuration failure without the rejected
    # limit value.
    return ModelInteractionError(
        category=_CONFIGURATION_CATEGORY,
        phase=_DECODING_PHASE,
        code=_CONFIGURATION_CODE,
        message=_LIMIT_MESSAGE,
    )


def _invalid_chunk_error() -> ModelInteractionError:
    """Create the failure for a chunk that is not immutable bytes."""
    # The diagnostic does not include the rejected object or its repr.
    return ModelInteractionError(
        category=_DESERIALIZATION_CATEGORY,
        phase=_DECODING_PHASE,
        code=_DESERIALIZATION_CODE,
        message=_CHUNK_MESSAGE,
    )


def _response_body_too_large_error() -> ModelInteractionError:
    """Create the failure for a body that would exceed its limit."""
    # The diagnostic does not include source bytes or the accumulated length.
    return ModelInteractionError(
        category=_DESERIALIZATION_CATEGORY,
        phase=_DECODING_PHASE,
        code=_TOO_LARGE_CODE,
        message=_TOO_LARGE_MESSAGE,
    )
