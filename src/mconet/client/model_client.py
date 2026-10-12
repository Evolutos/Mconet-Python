"""Reusable client that unifies unary interaction and close."""

from __future__ import annotations

from typing import cast

from mconet.core.domain.model_output import ModelOutput
from mconet.core.domain.model_request import ModelRequest
from mconet.core.domain.open_identifier import OpenIdentifier
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
from mconet.core.spi.component_ownership import ComponentOwnership
from mconet.core.spi.interaction_options import InteractionOptions
from mconet.core.spi.model_client_configuration import ModelClientConfiguration

_APPLICATION_OWNER = ComponentOwnership(OpenIdentifier("application"))


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

    __slots__ = ("_accepting_requests", "_configuration")

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
        # Open is the only state this construction establishes. Closing the
        # client, and refusing later requests, are separate lifecycle steps.
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
            ModelInteractionError: If the single runtime rejects the interaction.
        """
        request_value = cast(object, request)
        options_value = cast(object, options)
        # Close has already stopped this client. Argument checks and the
        # runtime stay unused so a late call cannot start another interaction.
        if not self._accepting_requests:
            raise RuntimeError("The client is not accepting requests.")
        if not isinstance(request_value, ModelRequest):
            raise TypeError("request must be a ModelRequest.")
        if not isinstance(options_value, InteractionOptions):
            raise TypeError("options must be an InteractionOptions.")
        return await execute_interaction(
            request_value,
            options_value,
            self._configuration,
        )

    async def close(self) -> None:
        """Stop this client from accepting later interactions.

        A second call leaves the client stopped and does not raise. Injected
        components stay open, and an interaction that already entered the
        runtime is not cancelled here.
        """
        # The flag is the whole transition. Component release is selected by
        # ownership in a later step and must not run for every close.
        self._accepting_requests = False
