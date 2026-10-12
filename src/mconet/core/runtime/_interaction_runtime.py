"""The one unary interaction runtime used by the public client."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import cast

from mconet.core.domain.bytes_value import Bytes
from mconet.core.domain.compatibility_policy import CompatibilityPolicy
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
from mconet.core.spi.authorization_context import AuthorizationContext
from mconet.core.spi.authorization_handler import AuthorizationHandler
from mconet.core.spi.authorization_handler_resolver import (
    AuthorizationHandlerResolver,
)
from mconet.core.spi.interaction_options import InteractionOptions
from mconet.core.spi.model_client_configuration import ModelClientConfiguration
from mconet.core.spi.model_integration_plan import ModelIntegrationPlan
from mconet.core.spi.model_integration_resolver import ModelIntegrationResolver
from mconet.core.spi.monitoring_event import MonitoringEvent
from mconet.core.spi.runtime_components import RuntimeComponents
from mconet.core.spi.service_access_resolver import ServiceAccessResolver
from mconet.core.spi.task_protocol_adapter import TaskProtocolAdapter

_UNARY_MODE_ID = OpenIdentifier("unary")
_HTTP_TRANSPORT_KIND = OpenIdentifier("http")
_NANOSECONDS_PER_SECOND = 1_000_000_000
_SDK_LIMITS = ResolvedInteractionResourceLimits(
    16_777_216,
    1_048_576,
    2_097_152,
)
_SDK_COMPONENTS = RuntimeComponents()
_SERVICE_ACCESS_RESOLVER = DefaultServiceAccessResolver()
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


async def execute_interaction(
    request: ModelRequest,
    options: InteractionOptions,
    configuration: ModelClientConfiguration,
) -> ModelOutput:
    """Run one unary interaction through the existing success pipeline.

    Public entries call this function instead of encoding or sending on their
    own. Configuration data is merged by the existing resolver. Component
    precedence stays in the existing selection schedule. After the snapshot is
    frozen, execution continues only through ``run_mock_transport_success``.

    Monitor merging and raw-response capture are not applied here. An absent
    service-access or authorization-handler resolver uses the builtin field
    merger or handler selector. An absent adapter and resolver fails with the
    existing unsupported-integration error.

    Args:
        request: Complete model request for this interaction.
        options: Overrides that apply only to this interaction.
        configuration: Reusable client defaults. This object is not modified.

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
            sdk_defaults=_SDK_COMPONENTS,
        )
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
        return await run_mock_transport_success(
            request=candidate_request,
            components=components,
            execution_plan=execution_plan,
            authorization_context=authorization_context,
            transport_context=transport_context,
            interaction_context=context,
            resources=resources,
            monitors=(),
            completed_event=completed,
            assembler=_ASSEMBLER,
            policy=resolved.compatibility_policy,
            output_id=interaction_id,
        )
    except BaseException:
        # The success chain releases the context on both return and failure.
        # Stages before that call must still drop the one-shot references.
        if not context.released:
            context.release()
        raise


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
) -> tuple[AuthorizationHandler, ...]:
    """Return the first non-empty handler tuple from interaction, then client."""
    for components in (options.components, configuration.components):
        if components is None or not components.authorization_handlers:
            continue
        return components.authorization_handlers
    return ()


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


def _now() -> Timestamp:
    """Read the clock once as a UTC timestamp."""
    nanoseconds = time.time_ns()
    seconds, fraction = divmod(nanoseconds, _NANOSECONDS_PER_SECOND)
    return Timestamp(seconds, fraction)
