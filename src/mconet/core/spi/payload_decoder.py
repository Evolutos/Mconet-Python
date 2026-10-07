"""Contract for decoding response bytes into protocol-native payloads."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from mconet.core.domain import Bytes
from mconet.core.spi.erased_runtime_value import ErasedRuntimeValue
from mconet.core.spi.runtime_component import RuntimeComponent


@runtime_checkable
class PayloadDecoder(RuntimeComponent, Protocol):
    """Decode one complete byte sequence into a protocol-native payload.

    Implementations parse immutable response bytes according to their declared
    component type contract and return the native object behind
    :class:`ErasedRuntimeValue`. Core selects and fixes the decoder before the
    request is sent, then validates actual response metadata separately.

    The contract deliberately excludes transport, media-type-driven component
    replacement, authorization, task and message interpretation, output assembly,
    and retry policy. Ordinary structural classes can implement it without SDK
    inheritance or a platform-specific generic wrapper.
    """

    def decode(self, raw_data: Bytes) -> ErasedRuntimeValue:
        """Decode complete bytes without selecting components or performing I/O."""
        # Decoding is synchronous for the current complete-byte response model.
        # Task adapters and message mappers interpret the returned value later.
        ...
