"""Bounded reading of an HTTP response body."""

from __future__ import annotations

from collections.abc import Iterable
from typing import cast

from mconet.core.domain.bytes_value import Bytes
from mconet.core.domain.error_category import ErrorCategory
from mconet.core.domain.interaction_phase import InteractionPhase
from mconet.core.domain.model_interaction_error import ModelInteractionError
from mconet.core.domain.open_identifier import OpenIdentifier

_MAX_SAFE_INTEGER = 2**53 - 1
_NETWORK_CATEGORY = ErrorCategory(OpenIdentifier("network"))
_CONFIGURATION_CATEGORY = ErrorCategory(
    OpenIdentifier("invalid_component_configuration")
)
_TRANSPORT_PHASE = InteractionPhase(OpenIdentifier("transport"))
_TOO_LARGE_CODE = "response_body_too_large"
_CONFIGURATION_CODE = "invalid_component_configuration"
_TOO_LARGE_MESSAGE = "HTTP response body exceeds its byte limit."
_LIMIT_MESSAGE = "HTTP response body byte limit must be a positive safe integer."
_CHUNK_MESSAGE = "HTTP response chunk must be bytes."


def read_bounded_http_response_body(
    chunks: Iterable[bytes],
    max_byte_length: int,
) -> Bytes:
    """Copy response chunks that fit inside a positive byte limit.

    Each chunk is counted before it is kept. The first chunk that would make
    the total larger than ``max_byte_length`` is not copied, and no later
    chunk is pulled. The error does not retain source bytes or the accumulated
    length. An unusable limit fails before the first read. This function does
    not close a connection; stopping the iterator is the read boundary.

    Args:
        chunks: Ordered response chunks. Each chunk is measured by its length.
        max_byte_length: Maximum accepted total as a positive safe integer.

    Returns:
        A new :data:`Bytes` value containing every accepted byte in source
        order.

    Raises:
        TypeError: If a chunk is not ``bytes``.
        ModelInteractionError: If the limit is unusable, or the body would
            exceed it. The size failure uses code ``response_body_too_large``.
    """
    # Reject the limit before touching the source so a bad configuration cannot
    # be reported as an oversized body or consume response data.
    if not _is_positive_safe_integer(max_byte_length):
        raise _invalid_limit_error()

    accepted_chunks: list[bytes] = []
    accepted_byte_length = 0
    for raw_chunk in chunks:
        chunk = cast(object, raw_chunk)
        if not isinstance(chunk, bytes):
            # A mutable buffer cannot be measured as an immutable response
            # chunk. Fail without copying its contents.
            raise TypeError(_CHUNK_MESSAGE)

        # Compare against the remaining room so a huge chunk is not copied and
        # is not added into the accepted total.
        if len(chunk) > max_byte_length - accepted_byte_length:
            raise _response_body_too_large_error()

        accepted_chunks.append(chunk)
        accepted_byte_length += len(chunk)

    # Join only after every chunk fits. A failed call never reaches this copy.
    return Bytes(b"".join(accepted_chunks))


def _is_positive_safe_integer(value: object) -> bool:
    """Return whether a limit is a positive integer inside the safe range."""
    # Exact int membership excludes bool. The upper bound is the integer range
    # every platform can represent for a body limit.
    return type(value) is int and 0 < value <= _MAX_SAFE_INTEGER


def _invalid_limit_error() -> ModelInteractionError:
    """Create the failure for a body limit that cannot be enforced."""
    # The diagnostic identifies the configuration failure without the rejected
    # limit value.
    return ModelInteractionError(
        category=_CONFIGURATION_CATEGORY,
        phase=_TRANSPORT_PHASE,
        code=_CONFIGURATION_CODE,
        message=_LIMIT_MESSAGE,
    )


def _response_body_too_large_error() -> ModelInteractionError:
    """Create the failure for a body that would exceed its limit."""
    # The diagnostic does not include source bytes or the accumulated length.
    return ModelInteractionError(
        category=_NETWORK_CATEGORY,
        phase=_TRANSPORT_PHASE,
        code=_TOO_LARGE_CODE,
        message=_TOO_LARGE_MESSAGE,
    )
