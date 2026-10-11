"""Compatibility policy interpretation for the OpenAI-compatible adapter."""

from __future__ import annotations

from mconet.core.domain import CompatibilityPolicy, OpenIdentifier

# Only these standard modes allow data outside the frozen wire profile. Strict
# and every unknown future mode fail closed, because an unknown strategy must
# never silently send values the profile does not define.
_RELAXED_MODES = frozenset({OpenIdentifier("compatible"), OpenIdentifier("permissive")})


def enforces_wire_profile(policy: CompatibilityPolicy) -> bool:
    """Return whether request values must stay inside the frozen wire profile.

    Args:
        policy: Compatibility policy the adapter was constructed with.

    Returns:
        ``False`` for ``compatible`` and ``permissive``; ``True`` for
        ``strict`` and any mode this adapter does not know.
    """
    return policy.mode not in _RELAXED_MODES
