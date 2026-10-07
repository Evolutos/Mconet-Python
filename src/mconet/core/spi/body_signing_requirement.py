"""Immutable protocol requirements for authorization-time body signing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias, cast

from mconet.core.domain import OpenIdentifier

BodySigningMode: TypeAlias = Literal[
    "none",
    "precomputed_digest",
    "unsigned_payload",
    "buffered_digest",
    "chunked_signature",
]
"""Closed body-signing modes shared by protocol plans and authorization."""

_BODY_SIGNING_MODES = frozenset(
    (
        "none",
        "precomputed_digest",
        "unsigned_payload",
        "buffered_digest",
        "chunked_signature",
    )
)
_MAX_SIGNED_INT64 = (1 << 63) - 1


@dataclass(frozen=True, slots=True)
class BodySigningRequirement:
    """Describe protocol-acceptable body-signing behavior in preference order.

    The canonical no-signing requirement is ``required=False`` with only
    ``none`` accepted. Required signing keeps one or more non-``none`` modes for
    later handler resolution. This value records protocol facts only; it does
    not choose a handler, read credentials, inspect a body, or perform signing.
    """

    required: bool = False
    """Whether handler resolution must select a body-signing mode."""

    acceptable_modes: tuple[BodySigningMode, ...] = ("none",)
    """Distinct acceptable modes ordered from most to least preferred."""

    digest_algorithms: frozenset[OpenIdentifier] = frozenset()
    """Immutable digest algorithms acceptable to the target protocol."""

    max_buffer_bytes: int | None = None
    """Optional positive signed-64-bit limit for buffered signing."""

    def __post_init__(self) -> None:
        """Validate canonical absence, closed modes, and portable field shapes."""
        required = cast(object, self.required)
        acceptable_modes = cast(object, self.acceptable_modes)
        digest_algorithms = cast(object, self.digest_algorithms)
        max_buffer_bytes = cast(object, self.max_buffer_bytes)

        # Exact bool validation excludes 0 and 1, whose accidental acceptance
        # would make cross-language signing requirements depend on coercion.
        if type(required) is not bool:
            raise TypeError("BodySigningRequirement required must be a boolean.")

        # A tuple preserves protocol preference order and fixes membership before
        # authorization handler resolution begins.
        if not isinstance(acceptable_modes, tuple):
            raise TypeError("BodySigningRequirement acceptable_modes must be a tuple.")
        if not acceptable_modes:
            raise ValueError(
                "BodySigningRequirement acceptable_modes must not be empty."
            )

        # Modes are a deliberately closed protocol vocabulary. Validate both the
        # primitive type and known value before checking cross-field semantics.
        mode_values = cast(tuple[object, ...], acceptable_modes)
        seen_modes: set[str] = set()
        for mode in mode_values:
            if not isinstance(mode, str):
                raise TypeError(
                    "BodySigningRequirement acceptable_modes must contain strings."
                )
            if mode not in _BODY_SIGNING_MODES:
                raise ValueError(
                    "BodySigningRequirement acceptable_modes contains an "
                    f"unsupported mode: {mode!r}."
                )
            if mode in seen_modes:
                raise ValueError(
                    "BodySigningRequirement acceptable_modes must not contain "
                    "duplicates."
                )
            seen_modes.add(mode)

        # No signing has exactly one canonical representation. Conversely, a
        # required signature cannot choose none as a successful resolution.
        if required:
            if "none" in seen_modes:
                raise ValueError(
                    "BodySigningRequirement required signing cannot accept none."
                )
        elif mode_values != ("none",):
            raise ValueError(
                "BodySigningRequirement optional signing must accept only none."
            )

        # Frozenset supplies immutable set semantics for algorithm negotiation;
        # algorithms stay open so future digest names remain representable.
        if not isinstance(digest_algorithms, frozenset):
            raise TypeError(
                "BodySigningRequirement digest_algorithms must be a frozenset."
            )
        for algorithm in cast(frozenset[object], digest_algorithms):
            if not isinstance(algorithm, OpenIdentifier):
                raise TypeError(
                    "BodySigningRequirement digest_algorithms must contain "
                    "OpenIdentifier values."
                )

        # Python integers are unbounded, so enforce the positive portable Int64
        # field shape before evaluating whether the selected modes may use it.
        if max_buffer_bytes is not None:
            if type(max_buffer_bytes) is not int:
                raise TypeError(
                    "BodySigningRequirement max_buffer_bytes must be an integer "
                    "or None."
                )
            if not 1 <= max_buffer_bytes <= _MAX_SIGNED_INT64:
                raise ValueError(
                    "BodySigningRequirement max_buffer_bytes must be a positive "
                    "signed 64-bit integer."
                )

        # The no-signing form cannot carry unused signing metadata. Required
        # forms preserve algorithm and buffering facts for the later resolver.
        if not required and digest_algorithms:
            raise ValueError(
                "BodySigningRequirement none mode cannot declare digest algorithms."
            )
        if not required and max_buffer_bytes is not None:
            raise ValueError(
                "BodySigningRequirement none mode cannot declare max_buffer_bytes."
            )

        # A valid cap has meaning only when buffered signing is one of the
        # ordered choices; other modes must not carry ignored buffer metadata.
        if max_buffer_bytes is not None:
            if "buffered_digest" not in seen_modes:
                raise ValueError(
                    "BodySigningRequirement max_buffer_bytes requires buffered_digest."
                )

        # Buffered signing must always have an explicit finite cap so a later
        # handler cannot choose it and accidentally buffer an unbounded body.
        if "buffered_digest" in seen_modes and max_buffer_bytes is None:
            raise ValueError(
                "BodySigningRequirement buffered_digest requires max_buffer_bytes."
            )
