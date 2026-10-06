"""Internal deterministic assembly of validated model interaction output."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from mconet.core.domain.diagnostic import Diagnostic
from mconet.core.domain.extensions import Extensions
from mconet.core.domain.model_descriptor import ModelDescriptor
from mconet.core.domain.model_output import ModelOutput
from mconet.core.domain.model_request import ModelRequest
from mconet.core.domain.model_target import ModelTarget
from mconet.core.domain.model_target_validation import validate_model_target
from mconet.core.domain.model_task_result import ModelTaskResult
from mconet.core.domain.output_status import OutputStatus
from mconet.core.domain.parsed_task_response import ParsedTaskResponse
from mconet.core.domain.parsed_task_response_validation import (
    validate_parsed_task_response,
)
from mconet.core.domain.protocol_state import ProtocolState
from mconet.core.domain.token_usage import TokenUsage


@dataclass(frozen=True, slots=True)
class _AssembledModelOutput:
    """Store the one immutable output shape produced by Core Runtime."""

    id: str | None
    """Optional Runtime-supplied interaction output identity."""

    target: ModelTarget
    """Exact target retained from the originating request."""

    resolved_model: ModelDescriptor | None
    """Optional actual model reported in the parsed service response."""

    status: OutputStatus
    """Required status retained from the parsed service response."""

    result: ModelTaskResult
    """Task-neutral result retained from the parsed service response."""

    stop_reason: str | None
    """Optional provider stop reason retained without interpretation."""

    usage: TokenUsage | None
    """Optional provider token accounting retained without inference."""

    diagnostics: tuple[Diagnostic, ...]
    """Ordered immutable diagnostics supplied by the current Runtime execution."""

    protocol_state: tuple[ProtocolState, ...]
    """Ordered immutable state retained from the parsed service response."""

    extensions: Extensions
    """Unknown fields retained from the parsed service response."""


class ModelOutputAssembler:
    """Combine request, protocol, and Runtime-owned facts exactly once.

    This internal stateless component is the SDK's concrete construction path for
    ``ModelOutput``. It validates the target that will be published, validates the
    complete parsed response, and accepts only an immutable Diagnostic tuple.

    It does not validate the full request again, generate identifiers or
    diagnostics, inspect transport data, merge extension channels, project
    task-specific convenience values, or perform I/O.
    """

    __slots__ = ()

    def assemble(
        self,
        request: ModelRequest,
        parsed_response: ParsedTaskResponse,
        diagnostics: tuple[Diagnostic, ...],
        *,
        output_id: str | None = None,
    ) -> ModelOutput:
        """Assemble one immutable output from independently owned facts.

        Args:
            request: The originating request whose exact target is retained.
            parsed_response: Validated service-protocol result facts.
            diagnostics: Ordered diagnostics collected by the current Runtime.
            output_id: Optional Runtime-assigned output identity.

        Returns:
            A new immutable ModelOutput whose nested values retain their original
            identities and ownership.

        Raises:
            TypeError: If an input or nested field has invalid runtime storage.
            ValueError: If target or parsed-response semantics are invalid.
        """
        candidate_request = cast(object, request)
        # Require the complete structural request before reading target. Earlier
        # Runtime stages validate the full request; assembly revalidates only the
        # exact target it publishes and does not repeat Task or access policy.
        if not isinstance(candidate_request, ModelRequest):
            raise TypeError("request must implement ModelRequest.")
        target = validate_model_target(candidate_request.target)

        # Parsed response validation is the sole semantic gate for all service-
        # owned facts and explicitly preserves every absent optional field.
        response = validate_parsed_task_response(parsed_response)
        validated_diagnostics = _validate_diagnostics(cast(object, diagnostics))

        candidate_output_id = cast(object, output_id)
        # ID absence remains None. A present value is opaque Runtime text and is
        # never derived from request, result, transport, or extension identifiers.
        if candidate_output_id is not None and not isinstance(candidate_output_id, str):
            raise TypeError("output_id must be a string or None.")

        # Transfer each owner exactly once. In particular, target comes only from
        # the request, diagnostics only from Runtime, and every remaining value
        # comes only from ParsedTaskResponse without merging or reconstruction.
        return _AssembledModelOutput(
            id=output_id,
            target=target,
            resolved_model=response.resolved_model,
            status=response.status,
            result=response.result,
            stop_reason=response.stop_reason,
            usage=response.usage,
            diagnostics=validated_diagnostics,
            protocol_state=response.protocol_state,
            extensions=response.extensions,
        )


def _validate_diagnostics(value: object) -> tuple[Diagnostic, ...]:
    """Require one ordered immutable collection of Runtime Diagnostic values."""
    # Tuple membership cannot change between assembly and observation; a list is
    # rejected rather than copied so Runtime must explicitly freeze its snapshot.
    if not isinstance(value, tuple):
        raise TypeError("diagnostics must be a tuple.")
    snapshot = cast(tuple[object, ...], value)
    if any(not isinstance(diagnostic, Diagnostic) for diagnostic in snapshot):
        raise TypeError("diagnostics must contain Diagnostic values.")

    # Return the same tuple rather than allocating another container, preserving
    # both Runtime order and the identity of its completed diagnostic snapshot.
    return cast(tuple[Diagnostic, ...], value)
