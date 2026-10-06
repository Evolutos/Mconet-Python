"""Open compatibility policy modes for interaction processing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from mconet.core.domain.open_identifier import (
    OpenIdentifier,
    validate_open_identifier,
)

_DEFAULT_MODE = OpenIdentifier("compatible")


@dataclass(frozen=True, slots=True)
class CompatibilityPolicy:
    """Represent a standard or future compatibility strategy.

    Standard modes are ``strict``, ``compatible``, and ``permissive``. The
    identifier remains open so integrations and later SDK versions can carry a
    new strategy without replacing it with a generic fallback or closed enum.
    This value only names policy; processing components own its behavior.
    """

    mode: OpenIdentifier
    """The validated open identifier naming the compatibility strategy."""

    def __post_init__(self) -> None:
        """Require a nominal, portable open mode without closing its value set."""
        mode = cast(object, self.mode)
        # Validate the shared identifier grammar but never compare with a fixed
        # list, which preserves unknown future strategies byte-for-byte.
        if not isinstance(mode, OpenIdentifier):
            raise TypeError("CompatibilityPolicy mode must be an OpenIdentifier.")
        validate_open_identifier(mode)

    def __str__(self) -> str:
        """Return the exact compatibility mode identifier text."""
        # String conversion is a lossless serialization boundary for both known
        # and unknown policy modes; it performs no fallback or normalization.
        return self.mode.value


def default_compatibility_policy() -> CompatibilityPolicy:
    """Create the stable compatible policy used when no override is supplied.

    Returns:
        A validated immutable policy whose mode is ``compatible``.
    """
    # Construct through the public value path so the default receives the same
    # validation and value semantics as caller-supplied modes. The shared mode
    # identifier is safe because OpenIdentifier is immutable.
    return CompatibilityPolicy(_DEFAULT_MODE)
