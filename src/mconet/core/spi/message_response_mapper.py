"""Message-subdomain contract for parsing decoded protocol response fragments."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from mconet.core.spi.erased_runtime_value import ErasedRuntimeValue
from mconet.core.spi.message_mapping_result import MessageMappingResult
from mconet.core.spi.runtime_component import RuntimeComponent


@runtime_checkable
class MessageResponseMapper(RuntimeComponent, Protocol):
    """Map one decoded protocol fragment to an atomic message result.

    Implementations interpret only the message subdomain, including message
    ordering, roles, relations, content, and response-local artifact references.
    The result keeps the complete :class:`~mconet.core.domain.MessageDocument`
    and its :class:`~mconet.core.domain.ArtifactCatalog` together so a caller
    cannot observe a document whose referenced artifacts were discarded.

    The contract deliberately excludes byte decoding, transport, authorization,
    task-result construction, catalog merging, and global artifact lookup.
    Ordinary structural classes can implement it without SDK inheritance or a
    platform-specific generic wrapper.
    """

    def map_response(self, fragment: ErasedRuntimeValue) -> MessageMappingResult:
        """Map one decoded fragment while preserving its complete artifact scope."""
        # Mapping is synchronous and starts after byte decoding. Returning one
        # pair makes message and artifact publication an indivisible operation.
        ...
