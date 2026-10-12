"""Runtime stop when R1 validation fails before later stages."""

from __future__ import annotations

from typing import cast

from mconet.core.domain.interaction_mode import InteractionMode
from mconet.core.domain.model_interaction_error import ModelInteractionError
from mconet.core.domain.model_request import ModelRequest
from mconet.core.runtime._interaction_terminal_machine import (
    InteractionTerminalMachine,
)
from mconet.core.runtime._r1_validation import validate_r1_interaction
from mconet.core.spi.credential_source import CredentialSource
from mconet.core.spi.model_integration_resolver import ModelIntegrationResolver
from mconet.core.spi.transport import Transport


def run_validation_gate(
    request: ModelRequest,
    mode: InteractionMode,
    transport: Transport,
    resolver: ModelIntegrationResolver,
    credential_source: CredentialSource,
    machine: InteractionTerminalMachine,
) -> tuple[ModelRequest, InteractionMode]:
    """Validate one interaction before transport, resolution, or credentials.

    The later dependencies are accepted so a caller can observe that a failed
    gate does not send, resolve an integration, or read a credential. A
    ``ModelInteractionError`` fails the interaction once and is re-raised.

    Args:
        request: Public model request.
        mode: Interaction mode selected for the request.
        transport: Transport that must stay idle when validation fails.
        resolver: Integration resolver that must stay idle when validation fails.
        credential_source: Credential source that must stay idle on failure.
        machine: Terminal machine for this interaction.

    Returns:
        The validated request and mode when every R1 gate passes.

    Raises:
        TypeError: If a later dependency has an invalid type.
        ModelInteractionError: If validation fails. The machine is then failed.
    """
    transport_value = cast(object, transport)
    resolver_value = cast(object, resolver)
    credential_value = cast(object, credential_source)
    machine_value = cast(object, machine)
    if not isinstance(transport_value, Transport):
        raise TypeError("transport must implement Transport.")
    if not isinstance(resolver_value, ModelIntegrationResolver):
        raise TypeError("resolver must implement ModelIntegrationResolver.")
    if not isinstance(credential_value, CredentialSource):
        raise TypeError("credential_source must implement CredentialSource.")
    if not isinstance(machine_value, InteractionTerminalMachine):
        raise TypeError("machine must be an InteractionTerminalMachine.")
    try:
        return validate_r1_interaction(request, mode)
    except ModelInteractionError:
        # One terminal failure. The three dependencies stay unused.
        machine_value.fail()
        raise
