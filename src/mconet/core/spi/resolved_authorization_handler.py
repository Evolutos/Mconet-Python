"""Immutable authorization handler and body-signing selection result."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from mconet.core.spi.body_signing_requirement import BodySigningMode
from mconet.core.spi.component_descriptor import ComponentDescriptor
from mconet.core.spi.runtime_component import RuntimeComponent

_BODY_SIGNING_MODES = frozenset(
    (
        "none",
        "precomputed_digest",
        "unsigned_payload",
        "buffered_digest",
        "chunked_signature",
    )
)


@dataclass(frozen=True, slots=True)
class ResolvedAuthorizationHandler:
    """Bind one selected authorization component to one signing mode.

    Authorization handler resolution produces this value only after it has
    found one compatible concrete handler and one mode allowed by both the
    protocol plan and that handler. The pair is immutable so later credential
    resolution and authorization application cannot swap either decision.

    ``RuntimeComponent`` is Python's established type-erased storage boundary
    for behavior contracts introduced later in the implementation sequence.
    This value validates component metadata but does not choose candidates,
    inspect authorization data, read credentials, or negotiate signing modes.
    """

    handler: RuntimeComponent
    """Exact concrete authorization handler component selected for execution."""

    body_signing_mode: BodySigningMode
    """Exact compatible body-signing mode selected with the handler."""

    def __post_init__(self) -> None:
        """Require one concrete component and one defined signing mode."""
        handler = cast(object, self.handler)
        body_signing_mode = cast(object, self.body_signing_mode)

        # The result retains a concrete component instance rather than a name,
        # registry key, factory, candidate list, or descriptor-only placeholder.
        if not isinstance(handler, RuntimeComponent):
            raise TypeError(
                "ResolvedAuthorizationHandler handler must implement RuntimeComponent."
            )

        # Runtime-checkable structural protocols prove descriptor presence but
        # not its returned type. Require the nominal immutable metadata value so
        # monitoring, ownership, and later contract checks have stable facts.
        descriptor = cast(object, handler.descriptor)
        if not isinstance(descriptor, ComponentDescriptor):
            raise TypeError(
                "ResolvedAuthorizationHandler handler descriptor must be a "
                "ComponentDescriptor."
            )

        # The resolver supplies an already-selected closed mode. This value
        # validates the result but never selects a fallback or silently changes
        # an unsupported mode to none.
        if not isinstance(body_signing_mode, str):
            raise TypeError(
                "ResolvedAuthorizationHandler body_signing_mode must be a string."
            )
        if body_signing_mode not in _BODY_SIGNING_MODES:
            raise ValueError(
                "ResolvedAuthorizationHandler body_signing_mode is unsupported."
            )
