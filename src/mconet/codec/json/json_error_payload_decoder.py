"""Error decoder for one bounded UTF-8 JSON response body."""

from __future__ import annotations

from mconet.codec.json.json_success_payload_decoder import JsonSuccessPayloadDecoder
from mconet.core.domain import Bytes
from mconet.core.spi.component_descriptor import ComponentDescriptor
from mconet.core.spi.erased_runtime_value import ErasedRuntimeValue

_DECODER_NAME = "json-error-payload-decoder"
_DECODER_VERSION = "1.0.0"
_DESCRIPTOR = ComponentDescriptor(
    _DECODER_NAME,
    _DECODER_VERSION,
    "builtin",
)


class JsonErrorPayloadDecoder:
    """Decode one bounded JSON error body without retaining a second copy.

    Error and success decoding share one JSON reader so a failure cannot grow a
    parallel copy of the response bytes. This class is still a separate
    component: callers select it before transport and it publishes its own
    descriptor. It does not classify provider errors or attach the body to a
    failure. The error type contract is a separate metadata work item.
    """

    __slots__ = ("_json_decoder",)

    def __init__(self, max_body_bytes: int) -> None:
        """Create an error decoder that refuses bodies larger than the limit.

        Args:
            max_body_bytes: Maximum accepted UTF-8 body length as a positive
                safe integer.

        Raises:
            ModelInteractionError: If ``max_body_bytes`` cannot enforce a
                finite positive limit.
        """
        # The inner reader owns the single bounded copy. This wrapper does not
        # buffer the bytes again before or after that read.
        self._json_decoder = JsonSuccessPayloadDecoder(max_body_bytes)

    @property
    def descriptor(self) -> ComponentDescriptor:
        """Return diagnostic metadata distinct from the success decoder."""
        # A separate descriptor keeps error and success selection from sharing
        # one component identity. Decode does not read the name.
        return _DESCRIPTOR

    def decode(self, raw_data: Bytes) -> ErasedRuntimeValue:
        """Decode one complete error body into a JSON value.

        Args:
            raw_data: Caller-owned response bytes.

        Returns:
            An erased JSON value. Provider error fields stay inside that value.

        Raises:
            TypeError: If ``raw_data`` is not ``bytes``.
            ModelInteractionError: If the body is too large, is not valid
                UTF-8, or is not portable JSON. The error does not include the
                body.
        """
        # Delegate without catching. Wrapping the failure could copy the body
        # into a new message or exception chain.
        return self._json_decoder.decode(raw_data)
