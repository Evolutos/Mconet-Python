"""Runtime scheduling for a non-success transport outcome."""

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


def resolve_error_outcome_decoder(
    components: InteractionExecutionComponents,
    outcome: TransportOutcome,
) -> PayloadDecoder:
    """Return the error decoder already fixed on the execution snapshot.

    Every outcome other than ``success`` enters this branch, including
    ``service_error``, ``transport_error``, and a future open value. The
    returned object is the snapshot's error decoder. The success decoder is
    not consulted and neither decoder is invoked.

    Args:
        components: Frozen snapshot that owns both preselected decoders.
        outcome: Normalized transport outcome for this response.

    Returns:
        The snapshot's error decoder.

    Raises:
        TypeError: If an argument or the error decoder has an invalid type.
        ModelInteractionError: If the outcome is ``success``. The code is
            ``unexpected_transport_outcome``.
    """
    components_value = cast(object, components)
    outcome_value = cast(object, outcome)
    if not isinstance(components_value, InteractionExecutionComponents):
        raise TypeError("components must be an InteractionExecutionComponents.")
    if not isinstance(outcome_value, TransportOutcome):
        raise TypeError("outcome must be a TransportOutcome.")
    # Success has its own branch. Using the error decoder for it would parse a
    # successful body as a service failure.
    if outcome_value.id == _SUCCESS_OUTCOME_ID:
        raise _unexpected_outcome_error()

    decoder = cast(object, components_value.error_payload_decoder)
    if not isinstance(decoder, PayloadDecoder):
        raise TypeError("error_payload_decoder must implement PayloadDecoder.")
    return decoder


def _unexpected_outcome_error() -> ModelInteractionError:
    """Create the stable failure for a success outcome on this branch."""
    # The outcome identifier stays out of the message so a future open value
    # cannot become log text.
    return ModelInteractionError(
        category=_INVALID_REQUEST,
        phase=_RESPONSE_DECODING,
        code=_UNEXPECTED_OUTCOME_CODE,
        message=_UNEXPECTED_OUTCOME_MESSAGE,
    )
