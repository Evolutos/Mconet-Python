"""Runtime scheduling for one assembled model output."""

from __future__ import annotations

from typing import cast

from mconet.core.domain.diagnostic import Diagnostic
from mconet.core.domain.model_output import ModelOutput
from mconet.core.domain.model_request import ModelRequest
from mconet.core.domain.parsed_task_response import ParsedTaskResponse
from mconet.core.runtime.model_output_assembler import ModelOutputAssembler


def assemble_interaction_output(
    assembler: ModelOutputAssembler,
    request: ModelRequest,
    parsed_response: ParsedTaskResponse,
    diagnostics: tuple[Diagnostic, ...],
    *,
    output_id: str | None = None,
) -> ModelOutput:
    """Assemble one output through the existing ModelOutputAssembler.

    ``assemble`` is called once. Target stays owned by the request, status and
    usage stay owned by the parsed response, and diagnostics stay owned by the
    caller. This stage does not decode, parse, or build a second output.

    Args:
        assembler: Stateless assembler that owns output construction.
        request: Originating request whose target is published.
        parsed_response: Parsed service facts.
        diagnostics: Runtime diagnostics for this interaction.
        output_id: Optional runtime-assigned output identity.

    Returns:
        The model output returned by that single ``assemble`` call.

    Raises:
        TypeError: If an argument has an invalid type, or the assembler
            rejects an argument type.
        ValueError: If the assembler rejects target or response semantics.
    """
    assembler_value = cast(object, assembler)
    request_value = cast(object, request)
    response_value = cast(object, parsed_response)
    diagnostics_value = cast(object, diagnostics)
    output_id_value = cast(object, output_id)
    if not isinstance(assembler_value, ModelOutputAssembler):
        raise TypeError("assembler must be a ModelOutputAssembler.")
    if not isinstance(request_value, ModelRequest):
        raise TypeError("request must implement ModelRequest.")
    if not isinstance(response_value, ParsedTaskResponse):
        raise TypeError("parsed_response must be a ParsedTaskResponse.")
    if not isinstance(diagnostics_value, tuple):
        raise TypeError("diagnostics must be a tuple.")
    if output_id_value is not None and not isinstance(output_id_value, str):
        raise TypeError("output_id must be a string or None.")
    return assembler_value.assemble(
        request_value,
        response_value,
        cast(tuple[Diagnostic, ...], diagnostics_value),
        output_id=output_id_value,
    )
