"""Outcome-based dispatch between already preselected payload decoders."""

from __future__ import annotations

from typing import cast

from mconet.core.domain import OpenIdentifier
from mconet.core.spi import PayloadDecoder, TransportOutcome

_SUCCESS_OUTCOME_ID = OpenIdentifier("success")


def dispatch_payload_decoder(
    outcome: TransportOutcome,
    success_payload_decoder: PayloadDecoder,
    error_payload_decoder: PayloadDecoder,
) -> PayloadDecoder:
    """Return one preselected decoder for a normalized transport outcome.

    ``success`` is the only outcome routed to the successful-response decoder.
    Standard service and transport failures, plus future non-success open values,
    route to the error-response decoder without interpreting native status codes.

    Both decoder arguments are fixed before network I/O. This function validates
    their behavioral boundary, preserves exact instance identity, and neither
    resolves a replacement nor invokes decoder behavior.
    """
    outcome_value = cast(object, outcome)
    success_value = cast(object, success_payload_decoder)
    error_value = cast(object, error_payload_decoder)

    # Require the normalized nominal value rather than accepting a bare outcome
    # string. Native HTTP or RPC status interpretation remains transport-owned.
    if not isinstance(outcome_value, TransportOutcome):
        raise TypeError("outcome must be a TransportOutcome.")

    # Validate both sides before branching so a successful response cannot hide
    # a malformed error snapshot, and an error response cannot hide a malformed
    # success snapshot. A complete execution snapshot must contain both paths.
    if not isinstance(success_value, PayloadDecoder):
        raise TypeError("success_payload_decoder must be a PayloadDecoder.")
    if not isinstance(error_value, PayloadDecoder):
        raise TypeError("error_payload_decoder must be a PayloadDecoder.")

    # Exact open-identifier equality is intentionally asymmetric: only the one
    # standard success value enters the success path. Every other preserved open
    # value uses the error path rather than acquiring guessed success semantics.
    if outcome.id == _SUCCESS_OUTCOME_ID:
        return success_payload_decoder
    return error_payload_decoder
