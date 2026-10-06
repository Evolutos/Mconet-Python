"""Open read-only contract for one assembled model interaction output."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from mconet.core.domain.diagnostic import Diagnostic
from mconet.core.domain.extensions import Extensions
from mconet.core.domain.model_descriptor import ModelDescriptor
from mconet.core.domain.model_target import ModelTarget
from mconet.core.domain.model_task_result import ModelTaskResult
from mconet.core.domain.output_status import OutputStatus
from mconet.core.domain.protocol_state import ProtocolState
from mconet.core.domain.token_usage import TokenUsage


@runtime_checkable
class ModelOutput(Protocol):
    """Describe one immutable task-neutral output assembled by Runtime.

    Implementations expose request-owned target identity, service-parsed facts,
    Runtime diagnostics, and forward-compatible extensions as separate read-only
    values. The structural contract permits Runtime-owned implementations without
    requiring inheritance or registration for future task result families.

    Protocol adapters produce ``ParsedTaskResponse`` rather than this contract.
    Runtime alone combines that value with the original target and diagnostics;
    validation, assembly, task-specific projections, and transport state remain
    outside the output data surface.
    """

    @property
    def id(self) -> str | None:
        """Return the optional interaction output identity assigned by Runtime."""
        # Absence remains distinct from an empty or synthesized provider response
        # ID and cannot be inferred from transport, result, or request identities.
        ...

    @property
    def target(self) -> ModelTarget:
        """Return the exact model target retained from the originating request."""
        # Keeping request selection explicit lets callers compare intended routing
        # with resolved_model without mutating or replacing either owned value.
        ...

    @property
    def resolved_model(self) -> ModelDescriptor | None:
        """Return the optional actual model explicitly reported by the service."""
        # None means the service supplied no model fact; implementations must not
        # copy target.model into this independently owned response field.
        ...

    @property
    def status(self) -> OutputStatus:
        """Return the required protocol-derived output status."""
        # Status remains separate from stop reason, diagnostics, result content,
        # and exceptions so no sibling field implicitly reclassifies the output.
        ...

    @property
    def result(self) -> ModelTaskResult:
        """Return the task-neutral service result and its local Artifact scope."""
        # Depending on the open result protocol keeps conversation and future task
        # families behind one output boundary without task-specific top-level data.
        ...

    @property
    def stop_reason(self) -> str | None:
        """Return the optional provider stop reason without interpretation."""
        # Absence is not inferred from status, content, cancellation, or diagnostics;
        # present provider text remains an independent parsed protocol fact.
        ...

    @property
    def usage(self) -> TokenUsage | None:
        """Return optional provider-reported token accounting."""
        # None preserves an unreported usage object, while present counts retain
        # their own missing-versus-zero semantics and provider-specific extensions.
        ...

    @property
    def diagnostics(self) -> tuple[Diagnostic, ...]:
        """Return ordered immutable diagnostics collected by Runtime."""
        # Runtime observations are assembled once and remain separate from service
        # status, stop reason, protocol state, result metadata, and exceptions.
        ...

    @property
    def protocol_state(self) -> tuple[ProtocolState, ...]:
        """Return ordered immutable state facts parsed from the service protocol."""
        # State order is retained from ParsedTaskResponse and cannot be modified by
        # diagnostic aggregation or target restoration during output assembly.
        ...

    @property
    def extensions(self) -> Extensions:
        """Return unknown assembled-output fields preserved as portable JSON."""
        # Output extensions form their own forward-compatible channel and do not
        # absorb result, target, diagnostic, usage, or transport-owned data.
        ...
