"""Role mapping between MessageRole identifiers and OpenAI wire spellings."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from mconet.core.domain import (
    ErrorCategory,
    Extensions,
    InteractionPhase,
    MessageRole,
    ModelInteractionError,
    OpenIdentifier,
)
from mconet.integration.openai_compatible._wire import invalid_protocol_response

UNSUPPORTED_MESSAGE_ROLE_CODE = "unsupported_message_role"
"""Stable code for a request role the protocol has no spelling for."""

_EMPTY_EXTENSIONS: Extensions = MappingProxyType({})
_UNSUPPORTED_FEATURE = ErrorCategory(OpenIdentifier("unsupported_feature"))
_PROTOCOL_ADAPTATION = InteractionPhase(OpenIdentifier("protocol_adaptation"))


@dataclass(frozen=True, slots=True)
class _OpenAIMessageRole:
    """Expose one standard role read from an OpenAI-compatible response.

    ``raw_value`` keeps the exact wire spelling so the original value stays
    observable after the role is mapped to its portable identifier.
    """

    id: OpenIdentifier
    """Portable standard role identifier."""

    raw_value: str
    """Exact wire spelling the service sent."""

    @property
    def semantic(self) -> None:
        """Return no extra guidance; standard identifiers carry their meaning."""
        return None

    @property
    def extensions(self) -> Extensions:
        """Return the shared empty mapping; the wire role has no extra fields."""
        return _EMPTY_EXTENSIONS


# The R1 scope supports exactly these three roles, and the mapping is one to
# one in both directions. There is no fallback role for either direction.
_WIRE_BY_ROLE_ID: MappingProxyType[OpenIdentifier, str] = MappingProxyType(
    {
        OpenIdentifier("message.system"): "system",
        OpenIdentifier("message.user"): "user",
        OpenIdentifier("message.assistant"): "assistant",
    }
)
_ROLE_BY_WIRE: MappingProxyType[str, MessageRole] = MappingProxyType(
    {
        wire: _OpenAIMessageRole(role_id, wire)
        for role_id, wire in _WIRE_BY_ROLE_ID.items()
    }
)
_SUPPORTED_WIRE_ROLES = "assistant, system, or user"


def wire_role(role: MessageRole, *, enforce_profile: bool) -> str:
    """Return the wire spelling for one request message role.

    ``role.id`` selects the spelling of the three standard roles, and their
    ``raw_value`` is ignored. An unknown identifier is rejected when the wire
    profile is enforced. Otherwise the caller-supplied ``raw_value`` is sent
    unchanged, which keeps original data such as a service-specific role; an
    unknown role without ``raw_value`` still fails, because inferring a
    spelling from the identifier or ``semantic`` would be a guess.

    Args:
        role: Role of one request MessageEntry.
        enforce_profile: Whether the compatibility policy requires the frozen
            wire profile.

    Returns:
        ``"system"``, ``"user"``, ``"assistant"``, or, for an unknown role
        when the profile is relaxed, the role's ``raw_value``.

    Raises:
        ModelInteractionError: If the identifier is not a standard role and
            either the profile is enforced or the role has no ``raw_value``.
    """
    spelling = _WIRE_BY_ROLE_ID.get(role.id)
    if spelling is not None:
        return spelling
    raw_value = role.raw_value
    if enforce_profile or raw_value is None:
        # The identifier is SDK-side request data, not service text, so naming
        # it tells the caller exactly which entry needs a different role.
        raise ModelInteractionError(
            category=_UNSUPPORTED_FEATURE,
            phase=_PROTOCOL_ADAPTATION,
            code=UNSUPPORTED_MESSAGE_ROLE_CODE,
            message=(
                f"Message role {role.id} is not supported by the "
                "OpenAI-compatible chat completions protocol."
            ),
        )
    return raw_value


def domain_role(spelling: str, path: str) -> MessageRole:
    """Return the standard role for one response message wire spelling.

    Args:
        spelling: Exact ``role`` text of a response message.
        path: JSON Pointer of the role member, used only in failure messages.

    Returns:
        A standard role whose ``raw_value`` is ``spelling``.

    Raises:
        ModelInteractionError: If the spelling is not one of the three roles
            the protocol defines. Matching is exact and case-sensitive.
    """
    role = _ROLE_BY_WIRE.get(spelling)
    if role is None:
        raise invalid_protocol_response(path, f"must be {_SUPPORTED_WIRE_ROLES}")
    return role
