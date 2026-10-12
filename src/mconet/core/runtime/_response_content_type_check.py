"""Runtime scheduling for response Content-Type checks."""

from __future__ import annotations

from mconet.core.domain.compatibility_policy import CompatibilityPolicy
from mconet.core.domain.diagnostic import Diagnostic
from mconet.core.runtime._response_media_type_validation import (
    validate_response_media_type,
)
from mconet.core.spi.decoder_selection import DecoderSelection
from mconet.core.spi.payload_decoder import PayloadDecoder
from mconet.core.spi.transport_response_metadata import TransportResponseMetadata


def check_response_content_type(
    metadata: TransportResponseMetadata,
    selection: DecoderSelection,
    decoder: PayloadDecoder,
    policy: CompatibilityPolicy,
) -> tuple[PayloadDecoder, tuple[Diagnostic, ...]]:
    """Check the response media type against the decoder already chosen.

    The validator may accept the observation or fail it. It cannot replace
    ``decoder``. This stage does not call ``decode``.

    Args:
        metadata: Response facts, including the actual media type.
        selection: Decoder criteria fixed by the execution plan.
        decoder: Decoder already chosen for this outcome.
        policy: Compatibility policy for media-type comparison.

    Returns:
        The same decoder and any compatibility diagnostics.

    Raises:
        TypeError: If an argument has an invalid type.
        ModelInteractionError: If the media type is incompatible with the
            fixed decoder. The code is ``response_media_type_mismatch``.
    """
    # Validation reads the decoder contract and returns diagnostics. The
    # decoder object is returned unchanged so a mismatch cannot select another.
    diagnostics = validate_response_media_type(metadata, selection, decoder, policy)
    return decoder, diagnostics
