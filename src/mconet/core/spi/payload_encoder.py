"""Contract for encoding protocol-native payloads into transport bodies."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from mconet.core.spi.erased_runtime_value import ErasedRuntimeValue
from mconet.core.spi.runtime_component import RuntimeComponent
from mconet.core.spi.transport_body import TransportBody


@runtime_checkable
class PayloadEncoder(RuntimeComponent, Protocol):
    """Encode one protocol-native payload into a complete transport body.

    Implementations convert the native object carried by
    :class:`ErasedRuntimeValue` according to their declared component type
    contract. The returned :class:`TransportBody` contains immutable bytes and
    structured media-type metadata ready for the later authorization stage.

    The contract deliberately excludes task and message interpretation, access
    resolution, credential reading, authorization application, request mutation,
    transport, and response handling. Ordinary structural classes can implement
    it without SDK inheritance or a platform-specific generic wrapper.
    """

    def encode(self, payload: ErasedRuntimeValue) -> TransportBody:
        """Encode one payload without applying authorization or performing I/O."""
        # Encoding is synchronous for the current complete-byte body variant.
        # Authorization and transport consume the returned body in later stages.
        ...
