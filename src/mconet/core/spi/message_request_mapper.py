"""Message-subdomain contract for producing protocol request fragments."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from mconet.core.domain import MessageDocument
from mconet.core.spi.erased_runtime_value import ErasedRuntimeValue
from mconet.core.spi.runtime_component import RuntimeComponent


@runtime_checkable
class MessageRequestMapper(RuntimeComponent, Protocol):
    """Map a complete message document to one protocol-native request fragment.

    Implementations translate only the message subdomain, including message
    ordering, roles, relations, and content. The returned value remains a native,
    unencoded protocol fragment behind :class:`ErasedRuntimeValue`; the owning
    task adapter composes that fragment with task-level fields.

    The contract deliberately excludes byte encoding, transport, authorization,
    task configuration, component lookup, and mutable registry behavior. Ordinary
    structural classes can therefore implement it without SDK inheritance or a
    platform-specific generic wrapper.
    """

    def map_request(self, document: MessageDocument) -> ErasedRuntimeValue:
        """Map one validated document without changing its message semantics."""
        # Mapping is synchronous and produces an unencoded native fragment.
        # Codec, authorization, and transport remain separate pipeline stages.
        ...
