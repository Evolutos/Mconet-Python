"""Success-path scheduling through a mock transport."""

from __future__ import annotations

from mconet.core.domain.compatibility_policy import CompatibilityPolicy
from mconet.core.domain.model_output import ModelOutput
from mconet.core.domain.model_request import ModelRequest
from mconet.core.domain.uri import UriValue
from mconet.core.runtime._authorization_application import apply_authorization_handler
from mconet.core.runtime._authorization_handler_resolution import (
    resolve_interaction_authorization_handler,
)
from mconet.core.runtime._authorization_will_resolve import (
    publish_authorization_will_resolve,
)
from mconet.core.runtime._credential_read import read_interaction_credential
from mconet.core.runtime._interaction_context import InteractionContext
from mconet.core.runtime._interaction_terminal_machine import (
    InteractionTerminalMachine,
)
from mconet.core.runtime._model_output_assembly import assemble_interaction_output
from mconet.core.runtime._monitor_failure_isolation import (
    publish_isolated_monitor_chain,
)
from mconet.core.runtime._payload_decoding import decode_response_payload
from mconet.core.runtime._payload_encoding import encode_protocol_payload
from mconet.core.runtime._pre_authorization_snapshot_schedule import (
    create_pre_authorization_snapshot,
)
from mconet.core.runtime._protocol_request_build import build_protocol_request
from mconet.core.runtime._response_content_type_check import (
    check_response_content_type,
)
from mconet.core.runtime._response_parsing import parse_successful_task_response
from mconet.core.runtime._response_resource_release import ResponseResources
from mconet.core.runtime._success_outcome_branch import (
    resolve_success_outcome_decoder,
)
from mconet.core.runtime._transport_send import send_interaction_request
from mconet.core.runtime.model_output_assembler import ModelOutputAssembler
from mconet.core.spi.authorization_context import AuthorizationContext
from mconet.core.spi.interaction_execution_components import (
    InteractionExecutionComponents,
)
from mconet.core.spi.interaction_monitor import InteractionMonitor
from mconet.core.spi.monitoring_event import MonitoringEvent
from mconet.core.spi.mutable_transport_request import MutableTransportRequest
from mconet.core.spi.protocol_execution_plan import ProtocolExecutionPlan
from mconet.core.spi.transport_context import TransportContext
from mconet.core.spi.transport_request_plan import TransportRequestPlan


async def run_mock_transport_success(
    *,
    request: ModelRequest,
    components: InteractionExecutionComponents,
    execution_plan: ProtocolExecutionPlan,
    authorization_context: AuthorizationContext,
    transport_context: TransportContext,
    interaction_context: InteractionContext,
    resources: ResponseResources,
    monitors: tuple[InteractionMonitor, ...],
    completed_event: MonitoringEvent,
    assembler: ModelOutputAssembler,
    policy: CompatibilityPolicy,
    output_id: str | None = None,
) -> ModelOutput:
    """Run one successful mock-transport interaction and return its output.

    The frozen snapshot is used in pipeline order: build, encode, redact,
    resolve and apply authorization, send, decode the success outcome, parse,
    and assemble. The terminal transition is completed once. Response resources
    and the interaction context are released afterward. Monitor failures do
    not replace the assembled output.

    Args:
        request: Validated request whose target is published on the output.
        components: Frozen components, including the mock transport.
        execution_plan: Plan whose transport facts build the mutable request.
        authorization_context: Non-sensitive facts for credential and apply.
        transport_context: Deadline, cancellation, and limits for send.
        interaction_context: Context released after the terminal transition.
        resources: Body and connection released after the response is consumed.
        monitors: Monitors that observe the redacted and completed events.
        completed_event: Event published after the output exists.
        assembler: Assembler that owns the output value.
        policy: Media-type policy for the preselected success decoder.
        output_id: Optional runtime-assigned output identity.

    Returns:
        The assembled model output.

    Raises:
        TypeError: If a stage rejects an argument type.
        ModelInteractionError: If a stage rejects the interaction.
        Exception: If the mock transport or a stage fails unexpectedly.
    """
    try:
        request_plan = build_protocol_request(request, components, execution_plan)
        body = encode_protocol_payload(components, request_plan)
        transport_plan = execution_plan.transport_plan
        mutable = MutableTransportRequest(
            transport_plan.method,
            _transport_url(transport_plan),
            transport_plan.headers,
            transport_plan.query,
            body,
        )
        redacted = create_pre_authorization_snapshot(
            mutable,
            transport_plan.authorization,
        )
        await publish_authorization_will_resolve(
            event_id=f"{authorization_context.interaction_id}.will_resolve",
            interaction_id=authorization_context.interaction_id,
            snapshot=redacted,
            monitors=monitors,
            timestamp=authorization_context.timestamp,
        )
        resolved = resolve_interaction_authorization_handler(
            components,
            transport_plan.authorization,
            transport_plan.body_signing_requirement,
        )
        await read_interaction_credential(
            transport_plan.authorization,
            authorization_context,
        )
        authorized = await apply_authorization_handler(
            resolved,
            transport_plan.authorization,
            authorization_context,
            mutable,
        )
        response = await send_interaction_request(
            components,
            authorized.freeze(),
            transport_context,
        )
        decoder = resolve_success_outcome_decoder(
            components,
            response.response_metadata.outcome,
        )
        decoder, diagnostics = check_response_content_type(
            response.response_metadata,
            execution_plan.success_decoder,
            decoder,
            policy,
        )
        decoded = decode_response_payload(decoder, response.body)
        parsed = parse_successful_task_response(components, decoded)
        output = assemble_interaction_output(
            assembler,
            request,
            parsed,
            diagnostics,
            output_id=output_id,
        )
        InteractionTerminalMachine().complete()
        await publish_isolated_monitor_chain(monitors, completed_event, output)
        return output
    finally:
        # Release even though this package only accepts the success path. A
        # later failure probe must not be required to teach the chain cleanup.
        resources.release()
        interaction_context.release()


def _transport_url(plan: TransportRequestPlan) -> UriValue:
    """Return the endpoint, appending a non-empty protocol path."""
    if plan.path == "":
        return plan.endpoint
    base = plan.endpoint.value
    path = plan.path if plan.path.startswith("/") else f"/{plan.path}"
    if base.endswith("/"):
        base = base[:-1]
    return UriValue(f"{base}{path}", plan.endpoint.is_absolute)
