"""Runtime decoding that still releases response resources on failure."""

from __future__ import annotations

from mconet.core.domain.bytes_value import Bytes
from mconet.core.domain.model_interaction_error import ModelInteractionError
from mconet.core.runtime._interaction_terminal_machine import (
    InteractionTerminalMachine,
)
from mconet.core.runtime._payload_decoding import decode_response_payload
from mconet.core.runtime._response_resource_release import ResponseResources
from mconet.core.spi.erased_runtime_value import ErasedRuntimeValue
from mconet.core.spi.payload_decoder import PayloadDecoder


def run_response_decoding(
    decoder: PayloadDecoder,
    raw_data: Bytes,
    resources: ResponseResources,
    machine: InteractionTerminalMachine,
) -> ErasedRuntimeValue:
    """Decode one body and release its resources afterward.

    A decoding failure fails the interaction once and still releases the body
    and connection. The decoding error propagates after that release.

    Args:
        decoder: Success or error decoder fixed before send.
        raw_data: Complete response bytes.
        resources: Body and connection owned by this response.
        machine: Terminal machine for this interaction.

    Returns:
        The decoded value.

    Raises:
        TypeError: If an argument has an invalid type.
        ModelInteractionError: If decoding fails. The machine is then failed
            and the resources have been released.
    """
    try:
        return decode_response_payload(decoder, raw_data)
    except ModelInteractionError:
        machine.fail()
        raise
    finally:
        resources.release()
