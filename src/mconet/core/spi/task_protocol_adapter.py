"""Task-neutral contract for mapping model interactions to service protocols."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from mconet.core.domain import (
    InteractionMode,
    ModelInteractionError,
    ModelRequest,
    ModelTarget,
    ParsedTaskResponse,
    ResolvedServiceAccess,
    TaskDescriptor,
)
from mconet.core.spi.erased_runtime_value import ErasedRuntimeValue
from mconet.core.spi.protocol_execution_plan import ProtocolExecutionPlan
from mconet.core.spi.protocol_request_plan import ProtocolRequestPlan
from mconet.core.spi.runtime_component import RuntimeComponent
from mconet.core.spi.transport_response_metadata import TransportResponseMetadata


@runtime_checkable
class TaskProtocolAdapter(RuntimeComponent, Protocol):
    """Map one task family and interaction mode to a target service protocol.

    Implementations are selected by target, task descriptor, and interaction
    mode. Planning is side-effect-free, request building produces a native
    protocol payload plus its fixed execution plan, and response parsing returns
    only service-protocol facts. Runtime remains the sole owner of top-level
    output assembly, component resolution, encoding, authorization, transport,
    monitoring, cancellation, and resource-limit enforcement.

    The contract is deliberately non-generic and uses ErasedRuntimeValue at the
    decoded response boundary so ordinary structural classes can implement it
    without SDK inheritance or platform-specific generic erasure wrappers.
    """

    def supports(
        self,
        target: ModelTarget,
        task: TaskDescriptor,
        mode: InteractionMode,
    ) -> bool:
        """Return whether this adapter handles the exact target/task/mode tuple."""
        # Applicability is a pure observation used before adapter selection. It
        # must not fetch credentials, inspect request bodies, or perform I/O.
        ...

    def prepare_plan(
        self,
        request: ModelRequest,
        access: ResolvedServiceAccess,
        mode: InteractionMode,
    ) -> ProtocolExecutionPlan:
        """Create immutable execution requirements without external side effects."""
        # Planning may read non-secret access conditions but cannot resolve a
        # credential, encode a payload, access one-shot content, or use transport.
        ...

    def build_request(
        self,
        request: ModelRequest,
        plan: ProtocolExecutionPlan,
    ) -> ProtocolRequestPlan:
        """Map a validated request into one protocol-native request plan."""
        # The returned native payload remains unencoded. PayloadEncoder owns byte
        # conversion, and authorization runs only after that encoding stage.
        ...

    def parse_response(
        self,
        response: ErasedRuntimeValue,
    ) -> ParsedTaskResponse:
        """Parse a decoded successful payload into service-reported task facts."""
        # The adapter must not construct ModelOutput or copy request target and
        # Runtime diagnostics into the parsed service response.
        ...

    def parse_error(
        self,
        error: ErasedRuntimeValue,
        metadata: TransportResponseMetadata,
    ) -> ModelInteractionError | None:
        """Map a decoded service error when the protocol recognizes its shape."""
        # None means this adapter cannot interpret the payload; Runtime retains
        # transport metadata and owns the fallback normalized error construction.
        ...
