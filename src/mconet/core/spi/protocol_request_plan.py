"""Immutable payload and execution-plan pair produced by protocol adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from mconet.core.spi.erased_runtime_value import ErasedRuntimeValue
from mconet.core.spi.protocol_execution_plan import ProtocolExecutionPlan


@dataclass(frozen=True, slots=True)
class ProtocolRequestPlan:
    """Pair one protocol payload with the plan governing its execution.

    A task protocol adapter produces this value without encoding the payload or
    performing I/O. The erased payload retains integration-owned runtime data,
    while the execution plan fixes the encoder, decoders, transport request,
    transport selection, mode components, and type contract used downstream.
    """

    payload: ErasedRuntimeValue
    """Protocol-native request payload awaiting the selected payload encoder."""

    execution_plan: ProtocolExecutionPlan
    """Complete immutable plan controlling encoding and request execution."""

    def __post_init__(self) -> None:
        """Require the established erased-value and execution-plan boundaries."""
        payload = cast(object, self.payload)
        execution_plan = cast(object, self.execution_plan)

        # The payload must carry portable type metadata together with the exact
        # native value; accepting a raw object would bypass component contracts.
        if not isinstance(payload, ErasedRuntimeValue):
            raise TypeError(
                "ProtocolRequestPlan payload must be an ErasedRuntimeValue."
            )

        # Retain the complete plan as one source of truth. Copying only its
        # transport plan would lose encoder, decoder, mode, and type requirements.
        if not isinstance(execution_plan, ProtocolExecutionPlan):
            raise TypeError(
                "ProtocolRequestPlan execution_plan must be a ProtocolExecutionPlan."
            )
