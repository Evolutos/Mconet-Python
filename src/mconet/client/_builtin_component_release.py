"""Release of builtin-owned components when a client closes."""

from __future__ import annotations

import inspect
from typing import cast

from mconet.core.runtime._component_ownership import determine_component_ownership
from mconet.core.spi.runtime_component import RuntimeComponent
from mconet.core.spi.runtime_components import RuntimeComponents

_BUILTIN_OWNER = "builtin"


async def release_builtin_client_components(
    sdk_defaults: RuntimeComponents,
    client_components: RuntimeComponents | None,
) -> None:
    """Close builtin-owned components and leave every other owner untouched.

    Ownership comes from exact instance membership. A component is closed only
    when it is an SDK default and the application did not also inject that same
    instance. ``close`` must be an asynchronous method. A component without
    ``close`` stays as it is. This function does not cancel an interaction.

    Args:
        sdk_defaults: Components the SDK created for this client.
        client_components: Components the application injected. Matching
            instances remain application-owned.

    Raises:
        TypeError: If a component carrier or candidate has an invalid type.
    """
    defaults = cast(object, sdk_defaults)
    application = cast(object, client_components)
    if not isinstance(defaults, RuntimeComponents):
        raise TypeError("sdk_defaults must be a RuntimeComponents.")
    if application is not None and not isinstance(application, RuntimeComponents):
        raise TypeError("client_components must be a RuntimeComponents or None.")

    # Walk the SDK instances in carrier order. Application membership is
    # decided by the existing ownership rule before any close call.
    for component in _instances(defaults):
        if not isinstance(component, RuntimeComponent):
            continue
        ownership = determine_component_ownership(
            component,
            interaction_components=None,
            client_components=application,
            sdk_defaults=defaults,
        )
        if ownership.id.value != _BUILTIN_OWNER:
            continue
        close = getattr(component, "close", None)
        # Only the asynchronous lifecycle operation is part of this release.
        # A missing close means the component holds nothing to free.
        if not inspect.iscoroutinefunction(close):
            continue
        await close()


def _instances(components: RuntimeComponents) -> tuple[object, ...]:
    """Return the present SDK instances in stable carrier order."""
    return (
        components.model_integration_resolver,
        components.task_protocol_adapter,
        components.service_access_resolver,
        components.payload_encoder,
        components.success_payload_decoder,
        components.error_payload_decoder,
        components.transport,
        components.authorization_handler_resolver,
        *components.authorization_handlers,
    )
