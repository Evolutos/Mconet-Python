"""Runtime scheduling for the successful transport outcome."""

from __future__ import annotations

from typing import cast

from mconet.core.domain.error_category import ErrorCategory
from mconet.core.domain.interaction_phase import InteractionPhase
from mconet.core.domain.model_interaction_error import ModelInteractionError
from mconet.core.domain.open_identifier import OpenIdentifier
from mconet.core.spi.interaction_execution_components import (
    InteractionExecutionComponents,
)
from mconet.core.spi.payload_decoder import PayloadDecoder
from mconet.core.spi.transport_outcome import TransportOutcome

_SUCCESS_OUTCOME_ID = OpenIdentifier("success")
_INVALID_REQUEST = ErrorCategory(OpenIdentifier("invalid_request"))
_RESPONSE_DECODING = InteractionPhase(OpenIdentifier("response_decoding"))
_UNEXPECTED_OUTCOME_CODE = "unexpected_transport_outcome"
_UNEXPECTED_OUTCOME_MESSAGE = (
    "The transport outcome does not match this decoder branch."
)


def resolve_success_outcome_decoder(
    components: InteractionExecutionComponents,
    outcome: TransportOutcome,
) -> PayloadDecoder:
    """Return the success decoder already fixed on the execution snapshot.

    Only the ``success`` outcome enters this branch. The returned object is
    the snapshot's success decoder. The error decoder is not consulted and
    neither decoder is invoked. A non-success outcome fails instead of
    selecting another decoder.

    Args:
        components: Frozen snapshot that owns both preselected decoders.
        outcome: Normalized transport outcome for this response.

    Returns:
        The snapshot's success decoder.

    Raises:
        TypeError: If an argument or the success decoder has an invalid type.
        ModelInteractionError: If the outcome is not ``success``. The code is
            ``unexpected_transport_outcome``.
    """
    components_value = cast(object, components)
    outcome_value = cast(object, outcome)
    if not isinstance(components_value, InteractionExecutionComponents):
        raise TypeError("components must be an InteractionExecutionComponents.")
    if not isinstance(outcome_value, TransportOutcome):
        raise TypeError("outcome must be a TransportOutcome.")
    # The error branch owns every other outcome. Falling through would hide a
    # service or transport failure behind the success decoder.
    if outcome_value.id != _SUCCESS_OUTCOME_ID:
        raise _unexpected_outcome_error()

    decoder = cast(object, components_value.success_payload_decoder)
    if not isinstance(decoder, PayloadDecoder):
        raise TypeError("success_payload_decoder must implement PayloadDecoder.")
    return decoder


def _unexpected_outcome_error() -> ModelInteractionError:
    """Create the stable failure for a non-success outcome on this branch."""
    # The outcome identifier stays out of the message so a future open value
    # cannot become log text.
    return ModelInteractionError(
        category=_INVALID_REQUEST,
        phase=_RESPONSE_DECODING,
        code=_UNEXPECTED_OUTCOME_CODE,
        message=_UNEXPECTED_OUTCOME_MESSAGE,
    )
