"""The one unary interaction runtime used by the public client."""

from __future__ import annotations

import time
from dataclasses import dataclass
from types import MappingProxyType
from typing import cast

from mconet.core.domain.authorization import Authorization
from mconet.core.domain.bytes_value import Bytes
from mconet.core.domain.compatibility_policy import CompatibilityPolicy
from mconet.core.domain.error_category import ErrorCategory
from mconet.core.domain.extensions import Extensions
from mconet.core.domain.header_field import HeaderField
from mconet.core.domain.headers import Headers
from mconet.core.domain.interaction_phase import InteractionPhase
from mconet.core.domain.json_value import JsonValue
from mconet.core.domain.model_interaction_error import ModelInteractionError
from mconet.core.domain.model_output import ModelOutput
from mconet.core.domain.model_request import ModelRequest
from mconet.core.domain.open_identifier import OpenIdentifier
from mconet.core.domain.resolved_interaction_resource_limits import (
    ResolvedInteractionResourceLimits,
)
from mconet.core.domain.timestamp import Timestamp
from mconet.core.runtime._cancellation_resolution import resolve_cancellation_signal
from mconet.core.runtime._component_selection_schedule import (
    select_execution_components,
)
from mconet.core.runtime._configuration_resolution import (
    resolve_interaction_configuration,
)
from mconet.core.runtime._deadline_resolution import resolve_transport_context
from mconet.core.runtime._direct_adapter_branch import resolve_direct_adapter
from mconet.core.runtime._execution_snapshot_schedule import (
    freeze_interaction_execution_components,
)
from mconet.core.runtime._integration_resolver_branch import (
    resolve_integration_binding,
)
from mconet.core.runtime._interaction_context import InteractionContext
from mconet.core.runtime._mock_transport_success import run_mock_transport_success
from mconet.core.runtime._model_integration_resolution_errors import (
    unsupported_model_integration_error,
)
from mconet.core.runtime._protocol_plan_preparation import (
    prepare_protocol_execution_plan,
)
from mconet.core.runtime._response_resource_release import ResponseResources
from mconet.core.runtime._service_access_resolution import resolve_service_access
from mconet.core.runtime.default_authorization_handler_resolver import (
    DefaultAuthorizationHandlerResolver,
)
from mconet.core.runtime.default_service_access_resolver import (
    DefaultServiceAccessResolver,
)
from mconet.core.runtime.interaction_configuration_layer import (
    InteractionConfigurationLayer,
)
from mconet.core.runtime.model_output_assembler import ModelOutputAssembler
from mconet.core.runtime.pre_authorization_snapshot import (
    omitted_authorization_header_names,
)
from mconet.core.spi.authorization_context import AuthorizationContext
from mconet.core.spi.authorization_handler import AuthorizationHandler
from mconet.core.spi.authorization_handler_resolver import (
    AuthorizationHandlerResolver,
)
from mconet.core.spi.component_role import ComponentRole
from mconet.core.spi.component_selection_resolution import (
    ComponentSelectionResolution,
)
from mconet.core.spi.interaction_monitor import InteractionMonitor
from mconet.core.spi.interaction_options import InteractionOptions
from mconet.core.spi.model_client_configuration import ModelClientConfiguration
from mconet.core.spi.model_integration_plan import ModelIntegrationPlan
from mconet.core.spi.model_integration_resolver import ModelIntegrationResolver
from mconet.core.spi.monitoring_event import MonitoringEvent
from mconet.core.spi.raw_response_snapshot import RawResponseSnapshot
from mconet.core.spi.runtime_components import RuntimeComponents
from mconet.core.spi.selected_component import SelectedComponent
from mconet.core.spi.service_access_resolver import ServiceAccessResolver
from mconet.core.spi.task_protocol_adapter import TaskProtocolAdapter
from mconet.core.spi.transport import Transport
from mconet.core.spi.transport_context import TransportContext
from mconet.core.spi.transport_request import TransportRequest
from mconet.core.spi.transport_response import TransportResponse
from mconet.core.spi.transport_response_metadata import TransportResponseMetadata

_INVALID_REQUEST = ErrorCategory(OpenIdentifier("invalid_request"))
_MONITORING_PHASE = InteractionPhase(OpenIdentifier("monitoring"))
_INVALID_MERGE_MODE_CODE = "invalid_monitoring_merge_mode"
_INVALID_MERGE_MODE_MESSAGE = "The monitoring merge mode is not supported."
_UNARY_MODE_ID = OpenIdentifier("unary")
_HTTP_TRANSPORT_KIND = OpenIdentifier("http")
_TRANSPORT_ROLE = ComponentRole(OpenIdentifier("transport.unary"))
_NANOSECONDS_PER_SECOND = 1_000_000_000
_SDK_LIMITS = ResolvedInteractionResourceLimits(
    16_777_216,
    1_048_576,
    2_097_152,
)
_SDK_COMPONENTS = RuntimeComponents()
_SERVICE_ACCESS_RESOLVER = DefaultServiceAccessResolver()
# Response snapshots use the same credential header names as the HTTP summary.
# Runtime cannot import transport, so the names are duplicated here.
_RESPONSE_CREDENTIAL_HEADER_NAMES = frozenset(
    {
        "authorization",
        "proxy-authorization",
        "cookie",
        "set-cookie",
    }
)
_AUTHORIZATION_HANDLER_RESOLVER = DefaultAuthorizationHandlerResolver()
_ASSEMBLER = ModelOutputAssembler()


@dataclass(frozen=True, slots=True)
class _UnaryMode:
    """Name the unary execution mode selected by this runtime."""

    @property
    def id(self) -> OpenIdentifier:
        """Return the unary mode identifier."""
        return _UNARY_MODE_ID


_UNARY_MODE = _UnaryMode()


class _ResponseRecorder:
    """Observe one transport response and return that same response."""

    __slots__ = ("_transport", "captured", "descriptor")

    def __init__(self, transport: Transport) -> None:
        """Retain the selected transport and its descriptor."""
        self._transport = transport
        self.descriptor = transport.descriptor
        self.captured: TransportResponse | None = None

    async def send(
        self,
        request: TransportRequest,
        context: TransportContext,
    ) -> TransportResponse:
        """Send through the selected transport and remember its response."""
        response = await self._transport.send(request, context)
        # The first response is the one decoding will read. Returning the same
        # object keeps the decoder on the transport's result.
        if self.captured is None:
            self.captured = response
        return response


class _OutputWithRawResponse:
    """Expose one assembled output plus an opted-in raw response."""

    __slots__ = ("_output", "raw_response")

    def __init__(self, output: ModelOutput, raw_response: RawResponseSnapshot) -> None:
        """Retain the assembled output and the snapshot beside it."""
        self._output = output
        self.raw_response = raw_response

    @property
    def id(self) -> str | None:
        """Return the assembled output identity."""
        return self._output.id

    @property
    def target(self) -> object:
        """Return the assembled output target."""
        return self._output.target

    @property
    def resolved_model(self) -> object:
        """Return the assembled resolved model."""
        return self._output.resolved_model

    @property
    def status(self) -> object:
        """Return the assembled output status."""
        return self._output.status

    @property
    def result(self) -> object:
        """Return the assembled task result."""
        return self._output.result

    @property
    def stop_reason(self) -> str | None:
        """Return the assembled stop reason."""
        return self._output.stop_reason

    @property
    def usage(self) -> object:
        """Return the assembled token usage."""
        return self._output.usage

    @property
    def diagnostics(self) -> object:
        """Return the assembled diagnostics."""
        return self._output.diagnostics

    @property
    def protocol_state(self) -> object:
        """Return the assembled protocol state."""
        return self._output.protocol_state

    @property
    def extensions(self) -> object:
        """Return the assembled extensions."""
        return self._output.extensions


async def execute_interaction(
    request: ModelRequest,
    options: InteractionOptions,
    configuration: ModelClientConfiguration,
    sdk_defaults: RuntimeComponents | None = None,
) -> ModelOutput:
    """Run one unary interaction through the existing success pipeline.

    Public entries call this function instead of encoding or sending on their
    own. Configuration data is merged by the existing resolver. Component
    precedence stays in the existing selection schedule. After the snapshot is
    frozen, execution continues only through ``run_mock_transport_success``.

    Monitor merging is not applied here. Raw-response capture runs only when
    the interaction options request it. An absent service-access or
    authorization-handler resolver uses the builtin field merger or handler
    selector. Encoder, decoder, transport, and authorization handlers fall
    through to ``sdk_defaults`` when no higher layer supplies them. An absent
    adapter and resolver fails with the existing unsupported-integration error.

    Args:
        request: Complete model request for this interaction.
        options: Overrides that apply only to this interaction.
        configuration: Reusable client defaults. This object is not modified.
        sdk_defaults: SDK-owned components. None uses an empty carrier.

    Returns:
        The assembled model output.

    Raises:
        TypeError: If an argument has an invalid nominal type.
        ValueError: If configuration cannot produce a target or limits.
        ModelInteractionError: If a runtime stage rejects the interaction.
    """
    candidate_request = cast(object, request)
    candidate_options = cast(object, options)
    candidate_configuration = cast(object, configuration)
    if not isinstance(candidate_request, ModelRequest):
        raise TypeError("request must be a ModelRequest.")
    if not isinstance(candidate_options, InteractionOptions):
        raise TypeError("options must be an InteractionOptions.")
    if not isinstance(candidate_configuration, ModelClientConfiguration):
        raise TypeError("configuration must be a ModelClientConfiguration.")
    candidate_defaults = cast(object, sdk_defaults)
    if candidate_defaults is None:
        candidate_defaults = _SDK_COMPONENTS
    elif not isinstance(candidate_defaults, RuntimeComponents):
        raise TypeError("sdk_defaults must be RuntimeComponents or None.")

    interaction_layer = InteractionConfigurationLayer(
        service_access=candidate_options.service_access_override,
        compatibility_policy=candidate_options.compatibility_policy,
        resource_limits=candidate_options.resource_limits,
        cancellation_signal=candidate_options.cancellation_signal,
    )
    client_layer = InteractionConfigurationLayer(
        target=candidate_configuration.default_target,
        service_access=candidate_configuration.default_service_access,
        compatibility_policy=candidate_configuration.default_compatibility_policy,
        resource_limits=candidate_configuration.default_resource_limits,
    )
    # Validation and the merge both happen inside this call. A failure returns
    # before an interaction context or a transport send exists.
    resolved = resolve_interaction_configuration(
        candidate_request,
        _UNARY_MODE,
        interaction_layer=interaction_layer,
        client_layer=client_layer,
        integration_layer=InteractionConfigurationLayer(),
        sdk_resource_limits=_SDK_LIMITS,
    )
    context = InteractionContext(candidate_request, resolved)
    try:
        plan = _integration_plan(
            candidate_request,
            candidate_options,
            candidate_configuration,
            resolved.compatibility_policy,
        )
        access_resolver = _service_access_resolver(
            candidate_options,
            candidate_configuration,
        )
        access = resolve_service_access(
            access_resolver,
            candidate_request,
            plan,
            interaction_layer=interaction_layer,
            client_layer=client_layer,
        )
        execution_plan = prepare_protocol_execution_plan(
            candidate_request,
            access,
            _UNARY_MODE,
            plan,
        )
        selection = select_execution_components(
            _UNARY_MODE,
            execution_plan,
            plan,
            interaction_components=candidate_options.components,
            client_components=candidate_configuration.components,
            sdk_defaults=candidate_defaults,
        )
        recorder: _ResponseRecorder | None = None
        # Default capture stays off. The selected transport is used directly,
        # so decoding still receives that transport's response object.
        if candidate_options.include_raw_response:
            recorder = _response_recorder(selection)
            selection = _selection_with_transport(selection, recorder)
        components = freeze_interaction_execution_components(
            integration_plan=plan,
            component_selection=selection,
            resource_limits=resolved.resource_limits,
            service_access_resolver=access_resolver,
            authorization_handler_resolver=_authorization_resolver(
                candidate_options,
                candidate_configuration,
            ),
            authorization_handlers=_authorization_handlers(
                candidate_options,
                candidate_configuration,
                candidate_defaults,
                plan,
            ),
            requirements=(),
        )
        interaction_id = str(context.identity)
        now = _now()
        cancellation = resolve_cancellation_signal(resolved)
        transport_context = resolve_transport_context(
            interaction_id=interaction_id,
            configuration=resolved,
            cancellation=cancellation,
            timeout=None,
            now=lambda: now,
        )
        endpoint = access.endpoint
        if endpoint is None:
            endpoint = execution_plan.transport_plan.endpoint
        kind = execution_plan.transport.transport_kind
        if kind is None:
            kind = _HTTP_TRANSPORT_KIND
        authorization_context = AuthorizationContext(
            interaction_id,
            resolved.target,
            endpoint,
            kind,
            now,
            execution_plan.transport_plan.body_signing_requirement.acceptable_modes[0],
            cancellation,
        )
        # The success chain releases these resources after it consumes the
        # transport response. This runtime does not decode that response itself.
        resources = ResponseResources(Bytes(b""), lambda: None)
        completed = MonitoringEvent(
            f"{interaction_id}.completed",
            OpenIdentifier("interaction.completed"),
            interaction_id,
            None,
            now,
            {"status": "completed"},
            {},
        )
        output = await run_mock_transport_success(
            request=candidate_request,
            components=components,
            execution_plan=execution_plan,
            authorization_context=authorization_context,
            transport_context=transport_context,
            interaction_context=context,
            resources=resources,
            monitors=_merged_monitors(candidate_options, candidate_configuration),
            completed_event=completed,
            assembler=_ASSEMBLER,
            policy=resolved.compatibility_policy,
            output_id=interaction_id,
        )
        if recorder is None or recorder.captured is None:
            return output
        captured = recorder.captured
        return cast(
            ModelOutput,
            _OutputWithRawResponse(
                output,
                _raw_snapshot(
                    captured,
                    resolved.resource_limits.max_response_body_bytes,
                    access.authorization,
                ),
            ),
        )
    except BaseException:
        # The success chain releases the context on both return and failure.
        # Stages before that call must still drop the one-shot references.
        if not context.released:
            context.release()
        raise


def _merged_monitors(
    options: InteractionOptions,
    configuration: ModelClientConfiguration,
) -> tuple[InteractionMonitor, ...]:
    """Combine client and interaction monitors without reading their events.

    A call that supplies no monitoring options uses the client monitors as
    stored. A call that supplies options uses that call's merge mode:
    ``append`` keeps client monitors first, ``prepend`` keeps interaction
    monitors first, and ``replace`` keeps only the interaction monitors,
    including an empty tuple that disables the client monitors. Body capture
    flags are not applied. An unknown mode fails before any monitor is called.
    """
    interaction = options.monitoring_options
    client = configuration.monitoring_defaults
    if interaction is None:
        if client is None:
            return ()
        return client.monitors
    mode = interaction.merge_mode.mode.value
    client_monitors = () if client is None else client.monitors
    interaction_monitors = interaction.monitors
    if mode == "append":
        return client_monitors + interaction_monitors
    if mode == "prepend":
        return interaction_monitors + client_monitors
    if mode == "replace":
        return interaction_monitors
    raise ModelInteractionError(
        category=_INVALID_REQUEST,
        phase=_MONITORING_PHASE,
        code=_INVALID_MERGE_MODE_CODE,
        message=_INVALID_MERGE_MODE_MESSAGE,
    )


def _integration_plan(
    request: ModelRequest,
    options: InteractionOptions,
    configuration: ModelClientConfiguration,
    policy: CompatibilityPolicy,
) -> ModelIntegrationPlan:
    """Choose the direct adapter branch or the injected resolver branch."""
    adapter = _component(options, configuration, "task_protocol_adapter")
    # An injected adapter is the direct branch. The resolver is not called.
    if isinstance(adapter, TaskProtocolAdapter):
        return resolve_direct_adapter(adapter, request, _UNARY_MODE)
    resolver = _component(options, configuration, "model_integration_resolver")
    if not isinstance(resolver, ModelIntegrationResolver):
        raise unsupported_model_integration_error()
    return resolve_integration_binding(resolver, request, _UNARY_MODE, policy)


def _service_access_resolver(
    options: InteractionOptions,
    configuration: ModelClientConfiguration,
) -> ServiceAccessResolver:
    """Return the injected access resolver, or the builtin field merger."""
    resolver = _component(options, configuration, "service_access_resolver")
    if isinstance(resolver, ServiceAccessResolver):
        return resolver
    return _SERVICE_ACCESS_RESOLVER


def _authorization_resolver(
    options: InteractionOptions,
    configuration: ModelClientConfiguration,
) -> AuthorizationHandlerResolver:
    """Return the injected handler resolver, or the builtin selector."""
    resolver = _component(options, configuration, "authorization_handler_resolver")
    if isinstance(resolver, AuthorizationHandlerResolver):
        return resolver
    return _AUTHORIZATION_HANDLER_RESOLVER


def _authorization_handlers(
    options: InteractionOptions,
    configuration: ModelClientConfiguration,
    sdk_defaults: RuntimeComponents,
    plan: ModelIntegrationPlan,
) -> tuple[AuthorizationHandler, ...]:
    """Return handlers from interaction, client, the binding, then SDK defaults."""
    for components in (options.components, configuration.components):
        if components is None or not components.authorization_handlers:
            continue
        return components.authorization_handlers
    binding_handlers = tuple(
        handler
        for handler in plan.authorization_handlers
        if isinstance(handler, AuthorizationHandler)
    )
    if binding_handlers:
        return binding_handlers
    return sdk_defaults.authorization_handlers


def _component(
    options: InteractionOptions,
    configuration: ModelClientConfiguration,
    field_name: str,
) -> object:
    """Return the first present component, interaction before client."""
    for components in (options.components, configuration.components):
        if components is None:
            continue
        value = getattr(components, field_name)
        if value is not None:
            return value
    return None


def _raw_snapshot(
    response: TransportResponse,
    max_response_body_bytes: int,
    authorization: Authorization,
) -> RawResponseSnapshot:
    """Retain metadata and withhold a body that exceeds the response limit.

    Credential header names are removed before the snapshot is stored. The
    length check does not allocate a prefix of the body. An over-limit
    snapshot stores an empty body and records that the octets were omitted.
    """
    body = response.body
    metadata = _redacted_metadata(response.response_metadata, authorization)
    if len(body) > max_response_body_bytes:
        return RawResponseSnapshot(Bytes(b""), metadata, body_omitted=True)
    return RawResponseSnapshot(body, metadata)


def _redacted_metadata(
    metadata: TransportResponseMetadata,
    authorization: Authorization,
) -> TransportResponseMetadata:
    """Copy response metadata without credential headers or secret names.

    Authorization, proxy authorization, cookies, API-key header names, and
    secret-named fields are omitted from headers, trailers, and extensions.
    A decision that names its own header, such as a header API key, omits
    that name too. The original metadata object is left unchanged for decoding.
    """
    omitted = _credential_header_names(authorization)
    return TransportResponseMetadata(
        metadata.outcome,
        _redacted_headers(metadata.headers, omitted),
        status_code=metadata.status_code,
        protocol_status_code=metadata.protocol_status_code,
        trailers=None
        if metadata.trailers is None
        else _redacted_headers(metadata.trailers, omitted),
        media_type=metadata.media_type,
        request_id=metadata.request_id,
        extensions=_redacted_extensions(metadata.extensions, omitted),
    )


def _credential_header_names(authorization: Authorization) -> frozenset[str]:
    """Return the header names that must not enter a raw response snapshot."""
    names = set(omitted_authorization_header_names(authorization))
    names.update(_RESPONSE_CREDENTIAL_HEADER_NAMES)
    return frozenset(names)


def _redacted_headers(headers: Headers, omitted: frozenset[str]) -> Headers:
    """Drop header fields whose names carry credentials or secrets."""
    retained: list[HeaderField] = []
    for header in headers.values:
        if _is_credential_name(header.name, omitted):
            continue
        retained.append(header)
    return Headers(tuple(retained))


def _redacted_extensions(
    extensions: Extensions,
    omitted: frozenset[str],
) -> Extensions:
    """Drop extension entries whose keys name credentials or secrets."""
    retained: dict[str, JsonValue] = {}
    for key, value in extensions.items():
        if _is_credential_name(key, omitted):
            continue
        retained[key] = value
    return MappingProxyType(retained)


def _is_credential_name(name: str, omitted: frozenset[str]) -> bool:
    """Return whether a field name would disclose a credential or a secret."""
    folded = name.casefold()
    if folded in omitted or "secret" in folded:
        return True
    compact = folded.replace("-", "").replace("_", "")
    return "apikey" in compact or "cookie" in folded or "authorization" in folded


def _response_recorder(selection: ComponentSelectionResolution) -> _ResponseRecorder:
    """Wrap the selected transport so capture can see its response."""
    for selected in selection.components:
        if selected.role != _TRANSPORT_ROLE:
            continue
        transport = selected.component
        if not isinstance(transport, Transport):
            raise TypeError("transport must implement Transport.")
        return _ResponseRecorder(transport)
    raise TypeError("transport must implement Transport.")


def _selection_with_transport(
    selection: ComponentSelectionResolution,
    recorder: _ResponseRecorder,
) -> ComponentSelectionResolution:
    """Return the selection with the recorder in the transport role."""
    replaced: list[SelectedComponent] = []
    for selected in selection.components:
        if selected.role == _TRANSPORT_ROLE:
            replaced.append(
                SelectedComponent(selected.role, recorder, recorder.descriptor)
            )
            continue
        replaced.append(selected)
    return ComponentSelectionResolution(tuple(replaced))


def _now() -> Timestamp:
    """Read the clock once as a UTC timestamp."""
    nanoseconds = time.time_ns()
    seconds, fraction = divmod(nanoseconds, _NANOSECONDS_PER_SECOND)
    return Timestamp(seconds, fraction)
