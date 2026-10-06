"""Immutable protocol-neutral token accounting reported by model services."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import cast

from mconet.core.domain.extensions import Extensions
from mconet.core.domain.json_value import JsonValue, validate_json_value_numbers

_EMPTY_EXTENSIONS: Extensions = MappingProxyType({})


def _empty_extensions() -> Extensions:
    """Return the shared immutable empty provider-extension mapping."""
    # Empty data has no nested mutable state and rejects membership changes, so
    # sharing it cannot couple independently constructed usage values.
    return _EMPTY_EXTENSIONS


@dataclass(frozen=True, slots=True)
class TokenUsage:
    """Carry optional provider-reported token counts without inference.

    Each standard count is independently optional: ``None`` means the provider
    did not report that field, while zero is an explicit reported value. Total
    tokens are preserved rather than computed or required to equal input plus
    output because providers may include cached, reasoning, or future categories.

    Extension data retains provider-specific usage breakdowns as portable JSON.
    Construction validates the complete value because no transport, mapper, or
    later consumer should need to repair token accounting after it is parsed.
    """

    input_tokens: int | None = None
    """Optional number of input tokens explicitly reported by the provider."""

    output_tokens: int | None = None
    """Optional number of output tokens explicitly reported by the provider."""

    total_tokens: int | None = None
    """Optional provider total preserved independently from component counts."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Read-only membership snapshot of provider-specific usage data."""

    def __post_init__(self) -> None:
        """Validate every count and freeze portable extension membership."""
        # Validate fields independently so absence and explicit zero remain
        # distinguishable and no count is inferred from either sibling value.
        for field_name, value in (
            ("input_tokens", cast(object, self.input_tokens)),
            ("output_tokens", cast(object, self.output_tokens)),
            ("total_tokens", cast(object, self.total_tokens)),
        ):
            _validate_count(value, field_name)

        # Detach outer mapping membership from caller mutation after all values
        # satisfy the shared recursive cross-platform JSON contract.
        object.__setattr__(self, "extensions", _snapshot_extensions(self.extensions))


def _validate_count(value: object, field_name: str) -> None:
    """Require one optional non-negative interoperable integer token count."""
    if value is None:
        # Missing provider fields remain absent rather than being forged as zero
        # or computed from the other standard count values.
        return
    # Exact membership excludes bool, floats, numeric text, and arbitrary integer-
    # like objects before arithmetic or serialization can observe them.
    if type(value) is not int:
        raise TypeError(f"TokenUsage {field_name} must be an integer or None.")
    if value < 0:
        raise ValueError(f"TokenUsage {field_name} must not be negative.")

    # Token counts cross JSON-based protocols, so enforce the common safe integer
    # range rather than relying on Python's unbounded integer representation.
    validate_json_value_numbers(cast(JsonValue, value))


def _snapshot_extensions(value: Extensions) -> Extensions:
    """Validate provider usage extensions and freeze mapping membership."""
    candidate = cast(object, value)
    # Accept custom read-only Mapping implementations while rejecting sequences,
    # scalars, and keys that cannot represent a portable JSON object.
    if not isinstance(candidate, Mapping):
        raise TypeError("TokenUsage extensions must be a mapping.")
    source = cast(Mapping[object, object], candidate)
    if any(not isinstance(key, str) for key in source):
        raise TypeError("TokenUsage extensions keys must be strings.")

    typed_source = cast(Mapping[str, JsonValue], source)
    # Validate recursive shape, cycles, safe integers, and finite floats before
    # exposing a read-only snapshot of the exact provider-owned values.
    for item in typed_source.values():
        validate_json_value_numbers(item)
    return MappingProxyType(dict(typed_source))
