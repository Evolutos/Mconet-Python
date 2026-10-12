"""Runtime scheduling for one payload decode."""

from __future__ import annotations

from typing import cast

from mconet.core.domain.bytes_value import Bytes
from mconet.core.domain.error_category import ErrorCategory
from mconet.core.domain.interaction_phase import InteractionPhase
from mconet.core.domain.model_interaction_error import ModelInteractionError
from mconet.core.domain.open_identifier import OpenIdentifier
from mconet.core.spi.erased_runtime_value import ErasedRuntimeValue
from mconet.core.spi.payload_decoder import PayloadDecoder

_PROTOCOL = ErrorCategory(OpenIdentifier("protocol"))
_DECODING = InteractionPhase(OpenIdentifier("decoding"))
_DECODING_FAILED_CODE = "payload_decoding_failed"
_DECODING_FAILED_MESSAGE = "The response payload could not be decoded."


def decode_response_payload(
    decoder: PayloadDecoder,
    raw_data: Bytes,
) -> ErasedRuntimeValue:
    """Decode one complete body with the decoder already chosen.

    ``decode`` is called once. A ``ModelInteractionError`` from the decoder is
    returned unchanged. Any other failure becomes one stable decoding error
    whose message does not include the body. The cause retains the original
    exception.

    Args:
        decoder: Success or error decoder fixed before the request was sent.
        raw_data: Complete response bytes.

    Returns:
        The erased value returned by that single ``decode`` call.

    Raises:
        TypeError: If an argument or the decoded value has an invalid type.
        ModelInteractionError: If decoding fails. An unknown failure uses
            ``payload_decoding_failed``.
    """
    decoder_value = cast(object, decoder)
    raw_value = cast(object, raw_data)
    if not isinstance(decoder_value, PayloadDecoder):
        raise TypeError("decoder must implement PayloadDecoder.")
    if not isinstance(raw_value, bytes):
        raise TypeError("raw_data must be a Bytes value.")

    try:
        decoded = decoder_value.decode(cast(Bytes, raw_value))
    except ModelInteractionError:
        raise
    except BaseException as error:
        # The body can contain a credential or a service payload. The stable
        # message excludes it, and the original exception stays on cause.
        raise ModelInteractionError(
            category=_PROTOCOL,
            phase=_DECODING,
            code=_DECODING_FAILED_CODE,
            message=_DECODING_FAILED_MESSAGE,
            cause=error,
        ) from error

    decoded_value = cast(object, decoded)
    if not isinstance(decoded_value, ErasedRuntimeValue):
        raise TypeError("decode must return an ErasedRuntimeValue.")
    return decoded_value
