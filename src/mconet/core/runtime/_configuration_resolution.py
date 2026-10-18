"""Runtime scheduling for one interaction's resolved configuration."""

from __future__ import annotations

from collections.abc import Callable

from mconet.core.domain.interaction_mode import InteractionMode
from mconet.core.domain.model_request import ModelRequest
from mconet.core.domain.resolved_interaction_resource_limits import (
    ResolvedInteractionResourceLimits,
)
from mconet.core.runtime._r1_validation import validate_r1_interaction
from mconet.core.runtime.interaction_configuration_layer import (
    InteractionConfigurationLayer,
)
from mconet.core.runtime.interaction_configuration_merge import (
    merge_interaction_configuration,
)
from mconet.core.runtime.resolved_configuration_validation import (
    validate_resolved_configuration,
)
from mconet.core.runtime.resolved_interaction_configuration import (
    ResolvedInteractionConfiguration,
)


def resolve_interaction_configuration(
    request: ModelRequest,
    mode: InteractionMode,
    *,
    interaction_layer: InteractionConfigurationLayer,
    client_layer: InteractionConfigurationLayer,
    integration_layer: InteractionConfigurationLayer,
    sdk_resource_limits: ResolvedInteractionResourceLimits,
    interaction_validation: Callable[
        [ModelRequest, InteractionMode],
        tuple[ModelRequest, InteractionMode],
    ] = validate_r1_interaction,
) -> ResolvedInteractionConfiguration:
    """Resolve one interaction's configuration without changing the client layer.

    R1 validation runs first. A failed request raises before any merge, so an
    invalid interaction cannot select or store configuration. The request layer
    is built for this call from the validated request's target and access. The
    interaction layer then overrides only the merge result. Nothing in that
    result is written back onto ``client_layer``.

    The redacted configuration snapshot is not created here. Monitoring builds
    that snapshot later from the returned value, and it is not stored on the
    client either.

    Args:
        request: The public model request for this interaction.
        mode: The interaction mode selected by the public entry.
        interaction_layer: Values that belong only to this interaction.
        client_layer: Reusable client defaults. This object is not modified.
        integration_layer: Defaults from the selected integration.
        sdk_resource_limits: Finite SDK byte limits used when no layer speaks.
        interaction_validation: Gate applied before the merge. The default is
            the unary text gate. The server-stream entry supplies its own.

    Returns:
        The validated configuration for this interaction alone.

    Raises:
        TypeError: If a request, mode, layer, or nested value has an invalid type.
        ValueError: If the request, target, access, or limits are invalid.
        ModelInteractionError: If the request or mode is outside the R1 scope.
    """
    # Validation failure stops the stage. The client layer is not read for a
    # merge and cannot receive this interaction's policy, limits, or signal.
    # The default gate is unary. A server-stream call passes its own gate so
    # this merge can run without accepting that mode on the unary entry.
    validated_request, _validated_mode = interaction_validation(request, mode)
    # Only request-owned target and access enter the request layer. Interaction
    # overrides stay on their own layer and are not copied onto the client.
    request_layer = InteractionConfigurationLayer(
        target=validated_request.target,
        service_access=validated_request.service_access,
    )
    merged = merge_interaction_configuration(
        interaction_layer=interaction_layer,
        request_layer=request_layer,
        client_layer=client_layer,
        integration_layer=integration_layer,
        sdk_resource_limits=sdk_resource_limits,
    )
    # Semantic validation returns the same merged object. It does not replace
    # the client layer or attach the result to a client.
    return validate_resolved_configuration(merged)
