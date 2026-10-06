"""Immutable default implementation of the open model descriptor contract."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import cast

from mconet.core.domain.extensions import Extensions
from mconet.core.domain.json_value import JsonValue
from mconet.core.domain.open_identifier import OpenIdentifier

_EMPTY_EXTENSIONS: Extensions = MappingProxyType({})


def _empty_extensions() -> Extensions:
    """Return the shared immutable empty mapping used by descriptor defaults."""
    # The mapping has no nested values and cannot be mutated, so sharing avoids
    # allocating a new empty proxy without creating shared mutable state.
    return _EMPTY_EXTENSIONS


@dataclass(frozen=True, slots=True)
class NamedModel:
    """Describe a model by an exact provider-facing name and optional facts.

    No field is inferred from ``name``. In particular, family and version stay
    ``None`` unless the caller explicitly supplies them. Metadata and extension
    mappings are copied and exposed through read-only views.
    """

    name: str
    """Required provider-facing model name preserved without normalization."""

    display_name: str | None = None
    """Optional human-readable model label."""

    family: OpenIdentifier | None = None
    """Optional explicitly supplied open model-family identifier."""

    version: str | None = None
    """Optional explicitly supplied producer version."""

    description: str | None = None
    """Optional human-readable model information."""

    metadata: Extensions = field(default_factory=_empty_extensions)
    """Read-only non-control metadata snapshot."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Read-only unknown-field snapshot for forward compatibility."""

    def __post_init__(self) -> None:
        """Require primitive field shapes and freeze mapping membership."""
        name = cast(object, self.name)
        display_name = cast(object, self.display_name)
        family = cast(object, self.family)
        version = cast(object, self.version)
        description = cast(object, self.description)

        # Construction checks storage types but deliberately leaves semantic
        # rules such as a non-empty name to the separate descriptor validator.
        if not isinstance(name, str):
            raise TypeError("NamedModel name must be a string.")
        for field_name, value in (
            ("display_name", display_name),
            ("version", version),
            ("description", description),
        ):
            if value is not None and not isinstance(value, str):
                raise TypeError(f"NamedModel {field_name} must be a string or None.")
        if family is not None and not isinstance(family, OpenIdentifier):
            raise TypeError("NamedModel family must be an OpenIdentifier or None.")

        # Snapshot only mapping membership here. JSON content validation belongs
        # to ModelDescriptor validation, while the read-only view prevents field
        # insertion or removal through this value object.
        object.__setattr__(
            self, "metadata", _snapshot_mapping(self.metadata, "metadata")
        )
        object.__setattr__(
            self,
            "extensions",
            _snapshot_mapping(self.extensions, "extensions"),
        )


def _snapshot_mapping(value: Extensions, field_name: str) -> Extensions:
    """Copy one string-keyed mapping and expose read-only membership."""
    candidate = cast(object, value)
    if not isinstance(candidate, Mapping):
        raise TypeError(f"NamedModel {field_name} must be a mapping.")
    source = cast(Mapping[object, object], candidate)
    if any(not isinstance(key, str) for key in source):
        raise TypeError(f"NamedModel {field_name} keys must be strings.")
    # Values remain exact JsonValue objects; this layer must not normalize or
    # reinterpret unknown metadata before the dedicated validator runs.
    snapshot = dict(cast(Mapping[str, JsonValue], source))
    return MappingProxyType(snapshot)
