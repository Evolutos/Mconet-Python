"""Runtime parsing that still releases the interaction context on failure."""

from __future__ import annotations

from mconet.core.domain.model_interaction_error import ModelInteractionError
from mconet.core.domain.parsed_task_response import ParsedTaskResponse
from mconet.core.runtime._interaction_context import InteractionContext
from mconet.core.runtime._interaction_terminal_machine import (
    InteractionTerminalMachine,
)
from mconet.core.runtime._response_parsing import parse_successful_task_response
from mconet.core.spi.erased_runtime_value import ErasedRuntimeValue
from mconet.core.spi.interaction_execution_components import (
    InteractionExecutionComponents,
)


def run_response_parsing(
    components: InteractionExecutionComponents,
    payload: ErasedRuntimeValue,
    context: InteractionContext,
    machine: InteractionTerminalMachine,
) -> ParsedTaskResponse:
    """Parse one success payload and release the interaction context afterward.

    A parsing failure fails the interaction once and still drops the context's
    callbacks and one-shot references. The parsing error propagates after that
    release.

    Args:
        components: Frozen snapshot whose adapter parses the payload.
        payload: Decoded successful payload.
        context: Interaction context released after parsing.
        machine: Terminal machine for this interaction.

    Returns:
        The parsed task response.

    Raises:
        TypeError: If an argument has an invalid type.
        ModelInteractionError: If parsing fails. The machine is then failed
            and the context has been released.
    """
    try:
        return parse_successful_task_response(components, payload)
    except ModelInteractionError:
        machine.fail()
        raise
    finally:
        context.release()
