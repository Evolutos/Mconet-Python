"""Reusable client that unifies unary interaction and close."""

from __future__ import annotations

from typing import cast

from mconet.auth.basic import (
    ApiKeyHeaderAuthorizationHandler,
    BearerAuthorizationHandler,
    NoAuthorizationHandler,
)
from mconet.client._builtin_component_release import (
    release_builtin_client_components,
)
from mconet.client._openai_compatible_binding import (
    OPENAI_COMPATIBLE_TYPE_KEY,
    openai_compatible_binding,
)
from mconet.client.text_request import model_request_from_text
from mconet.codec.json import (
    JsonErrorPayloadDecoder,
    JsonPayloadEncoder,
    JsonSuccessPayloadDecoder,
)
from mconet.core.domain.error_category import ErrorCategory
from mconet.core.domain.interaction_phase import InteractionPhase
from mconet.core.domain.model_interaction_error import ModelInteractionError
from mconet.core.domain.model_output import ModelOutput
from mconet.core.domain.model_request import ModelRequest
from mconet.core.domain.model_target import ModelTarget
from mconet.core.domain.open_identifier import OpenIdentifier
from mconet.core.domain.service_access import ServiceAccess
from mconet.core.runtime._integration_responsibility_chain import (
    IntegrationResponsibilityChain,
)
from mconet.core.runtime._integration_type_table import IntegrationTypeTable
from mconet.core.runtime._interaction_runtime import execute_interaction
from mconet.core.runtime._runtime_components_lifecycle_validation import (
    validate_runtime_components_lifecycle,
)
from mconet.core.runtime._runtime_components_spi_validation import (
    validate_runtime_components_spi,
)
from mconet.core.runtime._runtime_components_type_contract_validation import (
    validate_runtime_components_type_contracts,
)
from mconet.core.runtime.default_model_integration_resolver import (
    DefaultModelIntegrationResolver,
)
from mconet.core.spi.component_ownership import ComponentOwnership
from mconet.core.spi.interaction_options import InteractionOptions
from mconet.core.spi.model_client_configuration import ModelClientConfiguration
from mconet.core.spi.runtime_components import RuntimeComponents
from mconet.core.spi.transport import Transport
from mconet.transport.http_system import DefaultSystemHttpTransport

_APPLICATION_OWNER = ComponentOwnership(OpenIdentifier("application"))
_DEFAULT_MAX_RESPONSE_BODY_BYTES = 16_777_216
_INVALID_REQUEST = ErrorCategory(OpenIdentifier("invalid_request"))
_VALIDATION = InteractionPhase(OpenIdentifier("validation"))
_CLIENT_CLOSED_CODE = "client_closed"
_CLIENT_CLOSED_MESSAGE = "The client is closed."


class ModelClient:
    """Hold reusable client defaults and expose one interactor with close.

    The client stores the configuration it was constructed from and no
    interaction request, output, context, or session history. Injected
    components are checked before the client is retained. A failure there
    aborts construction instead of falling back to an SDK default.

    :meth:`interact` is the unary :class:`ModelInteractor` entry on this same
    object. Its execution belongs to the single interaction runtime. :meth:`close`
    is the client lifecycle entry on this same object. It does not close
    injected components and does not change whether new requests are accepted;
    those steps have their own lifecycle packages.

    The client is reusable: many interactions share this object, while each
    interaction keeps its own options and runtime state. The client starts
    accepting requests. Concurrent interactions stay on this same object.
    """

    __slots__ = ("_accepting_requests", "_configuration", "_sdk_defaults")

    def __init__(self, configuration: ModelClientConfiguration) -> None:
        """Retain one client configuration after its injected components pass.

        Args:
            configuration: Client defaults and direct component injection.

        Raises:
            TypeError: If ``configuration`` is not a ModelClientConfiguration,
                or an injected component has an invalid nominal shape.
            ModelInteractionError: If an injected component fails its behavior
                protocol, an adjacent type contract, or its lifecycle form.
        """
        candidate = cast(object, configuration)
        if not isinstance(candidate, ModelClientConfiguration):
            raise TypeError("configuration must be a ModelClientConfiguration.")
        components = candidate.components
        # Direct injection is application-owned. Validate the whole carrier
        # before this client can retain it, and do not replace a bad component.
        if components is not None:
            validate_runtime_components_spi(components)
            validate_runtime_components_type_contracts(components)
            validate_runtime_components_lifecycle(components, _APPLICATION_OWNER)
        self._configuration = candidate
        # SDK-created components are tracked apart from injected components.
        # Direct injection stays application-owned and is not released here.
        self._sdk_defaults = RuntimeComponents()
        self._accepting_requests = True

    @property
    def configuration(self) -> ModelClientConfiguration:
        """Return the configuration this reusable client retains."""
        return self._configuration

    async def interact(
        self,
        request: ModelRequest,
        options: InteractionOptions,
    ) -> ModelOutput:
        """Accept one unary interaction on this reusable client.

        Args:
            request: Complete model request for this interaction.
            options: Overrides that apply only to this interaction.

        Returns:
            The assembled model output from the single interaction runtime.

        Raises:
            TypeError: If an argument has an invalid nominal type.
            ModelInteractionError: If the client is closed, or the single
                runtime rejects the interaction. A closed client uses code
                ``client_closed``.
        """
        request_value = cast(object, request)
        options_value = cast(object, options)
        # Close has already stopped this client. Argument checks and the
        # runtime stay unused so a late call cannot start another interaction.
        if not self._accepting_requests:
            raise _client_closed_error()
        if not isinstance(request_value, ModelRequest):
            raise TypeError("request must be a ModelRequest.")
        if not isinstance(options_value, InteractionOptions):
            raise TypeError("options must be an InteractionOptions.")
        return await execute_interaction(
            request_value,
            options_value,
            self._configuration,
            self._sdk_defaults,
        )

    async def interact_text(
        self,
        target: ModelTarget,
        text: str,
        options: InteractionOptions | None = None,
        service_access: ServiceAccess | None = None,
    ) -> ModelOutput:
        """Run one text prompt through the same unary interaction entry.

        The prompt becomes one conversation model request. Execution is the
        existing :meth:`interact` call. This method does not encode, authorize,
        or send on its own.

        Args:
            target: Routing target for the generated request.
            text: Exact user text.
            options: Interaction overrides. None uses an empty options value.
            service_access: Optional access stored on the generated request.

        Returns:
            The model output returned by :meth:`interact`.

        Raises:
            TypeError: If an argument has an invalid nominal type.
            ModelInteractionError: If the client is closed or the runtime
                rejects the generated request.
        """
        request = model_request_from_text(target, text, service_access)
        candidate_options = cast(object, options)
        if candidate_options is None:
            candidate_options = InteractionOptions()
        if not isinstance(candidate_options, InteractionOptions):
            raise TypeError("options must be an InteractionOptions or None.")
        return await self.interact(request, candidate_options)

    async def close(self) -> None:
        """Stop this client from accepting later interactions.

        A second call leaves the client stopped and does not raise. Injected
        components stay open, and an interaction that already entered the
        runtime is not cancelled here.
        """
        # The acceptance flag is the whole transition. Builtin components are
        # released after the client has stopped accepting new requests.
        self._accepting_requests = False
        await release_builtin_client_components(
            self._sdk_defaults,
            self._configuration.components,
        )

    @classmethod
    def make_default(cls) -> ModelClient:
        """Return a client that injects no application components.

        Unset encoder, decoder, transport, and authorization roles use the
        JSON codec, the system HTTP transport, and the basic authorization
        handlers. Those objects are SDK-owned. ``close`` releases them. The
        returned configuration does not list them as injected components.

        Returns:
            A client that is accepting requests and owns the builtin components.
        """
        client = cls(ModelClientConfiguration())
        # Direct injection would mark these objects application-owned, so they
        # stay on the SDK carrier that close releases.
        client._sdk_defaults = _builtin_components()
        return client

    @classmethod
    def make_openai_compatible(
        cls,
        target: ModelTarget,
        service_access: ServiceAccess,
        *,
        max_response_body_bytes: int = _DEFAULT_MAX_RESPONSE_BODY_BYTES,
    ) -> ModelClient:
        """Return a client whose defaults are one OpenAI-compatible binding.

        The binding supplies the adapter, JSON codec, system HTTP transport,
        and basic authorization handlers. This factory adds the caller's
        target and service access. It does not build a second component set.

        Args:
            target: Default model target stored on the client.
            service_access: Default access stored on the client. The binding
                has no universal endpoint, so this access supplies it.
            max_response_body_bytes: Body limit passed to the binding's
                JSON decoders.

        Returns:
            A client that resolves chat completions through that binding.

        Raises:
            TypeError: If a target, access value, or body limit has the wrong type.
        """
        candidate_target = cast(object, target)
        candidate_access = cast(object, service_access)
        candidate_limit = cast(object, max_response_body_bytes)
        if not isinstance(candidate_target, ModelTarget):
            raise TypeError("target must be a ModelTarget.")
        if not isinstance(candidate_access, ServiceAccess):
            raise TypeError("service_access must be a ServiceAccess.")
        if type(candidate_limit) is not int:
            raise TypeError("max_response_body_bytes must be an integer.")
        binding = openai_compatible_binding(
            max_response_body_bytes=candidate_limit,
        )
        resolver = DefaultModelIntegrationResolver(
            IntegrationTypeTable(((OPENAI_COMPATIBLE_TYPE_KEY, binding),)),
            IntegrationResponsibilityChain(()),
        )
        client = cls(
            ModelClientConfiguration(
                default_target=candidate_target,
                default_service_access=candidate_access,
                components=RuntimeComponents(
                    model_integration_resolver=resolver,
                ),
            )
        )
        # The binding transport is SDK-owned so close can release it. Selection
        # still uses the same instance through the resolved binding.
        transport = binding.transports[0] if binding.transports else None
        if isinstance(transport, Transport):
            client._sdk_defaults = RuntimeComponents(transport=transport)
        return client


def _builtin_components() -> RuntimeComponents:
    """Build the JSON, system HTTP, and basic-authorization defaults."""
    # One shared limit matches the runtime's default response-body budget.
    # The transport ignores process proxy variables.
    return RuntimeComponents(
        payload_encoder=JsonPayloadEncoder(),
        success_payload_decoder=JsonSuccessPayloadDecoder(
            _DEFAULT_MAX_RESPONSE_BODY_BYTES
        ),
        error_payload_decoder=JsonErrorPayloadDecoder(_DEFAULT_MAX_RESPONSE_BODY_BYTES),
        transport=DefaultSystemHttpTransport(proxy_environment={}),
        authorization_handlers=(
            NoAuthorizationHandler(),
            BearerAuthorizationHandler(),
            ApiKeyHeaderAuthorizationHandler(),
        ),
    )


def _client_closed_error() -> ModelInteractionError:
    """Create the stable failure for a request that arrives after close."""
    # The message names the client state only. It does not include request
    # contents, component names, or resource identifiers.
    return ModelInteractionError(
        category=_INVALID_REQUEST,
        phase=_VALIDATION,
        code=_CLIENT_CLOSED_CODE,
        message=_CLIENT_CLOSED_MESSAGE,
    )
