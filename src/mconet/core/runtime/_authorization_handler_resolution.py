"""Runtime scheduling for authorization handler resolution."""

from __future__ import annotations

from typing import cast

from mconet.core.domain.authorization import Authorization
from mconet.core.spi.authorization_handler_resolver import (
    AuthorizationHandlerResolver,
)
from mconet.core.spi.body_signing_requirement import BodySigningRequirement
from mconet.core.spi.interaction_execution_components import (
    InteractionExecutionComponents,
)
from mconet.core.spi.resolved_authorization_handler import ResolvedAuthorizationHandler


def resolve_interaction_authorization_handler(
    components: InteractionExecutionComponents,
    authorization: Authorization,
    requirement: BodySigningRequirement,
) -> ResolvedAuthorizationHandler:
    """Resolve one handler from the frozen candidate tuple.

    The snapshot's resolver is called once with the snapshot's handlers. Zero
    matches and several matches stay the resolver's separate failures. This
    stage does not call ``apply`` or send the request.

    Args:
        components: Frozen snapshot that owns the resolver and candidates.
        authorization: Opaque decision to match.
        requirement: Protocol signing constraint for that decision.

    Returns:
        The unique handler and signing mode selected by the resolver.

    Raises:
        TypeError: If an argument or the snapshot resolver has an invalid type.
        ModelInteractionError: If no handler matches, or more than one matches.
    """
    components_value = cast(object, components)
    authorization_value = cast(object, authorization)
    requirement_value = cast(object, requirement)
    if not isinstance(components_value, InteractionExecutionComponents):
        raise TypeError("components must be an InteractionExecutionComponents.")
    if not isinstance(authorization_value, Authorization):
        raise TypeError("authorization must implement Authorization.")
    if not isinstance(requirement_value, BodySigningRequirement):
        raise TypeError("requirement must be a BodySigningRequirement.")

    resolver = cast(object, components_value.authorization_handler_resolver)
    # The frozen resolver is the only matcher. A caller-supplied resolver
    # cannot replace it after the snapshot exists.
    if not isinstance(resolver, AuthorizationHandlerResolver):
        raise TypeError(
            "authorization_handler_resolver must implement "
            "AuthorizationHandlerResolver."
        )
    return resolver.resolve(
        authorization_value,
        requirement_value,
        components_value.authorization_handlers,
    )
