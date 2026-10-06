"""Stable identifier lookup for isolated JSON schema documents."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from types import MappingProxyType
from typing import cast

from mconet.core.domain import (
    JsonValue,
    OpenIdentifier,
    validate_json_value_numbers,
    validate_open_identifier,
)


class SchemaLoader:
    """Load one registered JSON schema by its stable open identifier.

    The loader snapshots an explicitly supplied registry and exposes no global
    discovery or mutation API. Schema roots must be JSON objects. Every load
    returns an independent copy so validation adapters cannot alter the loader's
    canonical document or affect later consumers.
    """

    __slots__ = ("_schemas",)

    _schemas: Mapping[OpenIdentifier, dict[str, JsonValue]]

    def __init__(
        self,
        schemas: Mapping[OpenIdentifier, JsonValue],
    ) -> None:
        """Validate and snapshot a stable identifier-to-schema registry.

        Args:
            schemas: Explicit schema documents keyed by stable identifiers.

        Raises:
            TypeError: If the registry, a key, or a schema has an invalid type.
            ValueError: If an identifier or JSON number is invalid, or a schema
                root is not an object.
        """
        candidate = cast(object, schemas)
        if not isinstance(candidate, Mapping):
            raise TypeError("schemas must be a mapping.")

        source = cast(Mapping[object, object], candidate)
        snapshot: dict[OpenIdentifier, dict[str, JsonValue]] = {}
        for raw_identifier, raw_schema in source.items():
            # Stable names use the same open identifier grammar as other domain
            # registries; no closed schema-name list is embedded in the loader.
            if not isinstance(raw_identifier, OpenIdentifier):
                raise TypeError("Schema identifiers must be OpenIdentifier values.")
            validate_open_identifier(raw_identifier)

            # Validate the complete JSON document before narrowing its root to
            # an object, keeping malformed content distinct from wrong root kind.
            schema = cast(JsonValue, raw_schema)
            validate_json_value_numbers(schema)
            if not isinstance(schema, dict):
                raise ValueError("A schema document root must be a JSON object.")

            # Snapshot nested lists and objects so later caller mutation cannot
            # modify the registered canonical document.
            snapshot[raw_identifier] = deepcopy(schema)

        # The proxy prevents accidental registry mutation inside future loader
        # methods; nested values are never exposed directly.
        object.__setattr__(self, "_schemas", MappingProxyType(snapshot))

    def load(self, identifier: OpenIdentifier) -> dict[str, JsonValue]:
        """Return an independent copy of one schema document.

        Args:
            identifier: Stable identifier of the requested schema.

        Returns:
            A mutable copy of the requested JSON object document.

        Raises:
            TypeError: If ``identifier`` is not an OpenIdentifier.
            ValueError: If the identifier violates portable syntax.
            KeyError: If no schema is registered for the identifier.
        """
        candidate = cast(object, identifier)
        if not isinstance(candidate, OpenIdentifier):
            raise TypeError("identifier must be an OpenIdentifier.")
        validate_open_identifier(candidate)

        # Translate the raw mapping miss into a stable public diagnostic while
        # suppressing implementation details from the exception chain.
        try:
            schema = self._schemas[candidate]
        except KeyError:
            raise KeyError(f"Unknown schema identifier: {candidate.value}.") from None

        # Each consumer owns its returned tree and cannot mutate the registry or
        # another consumer's previously loaded schema.
        return deepcopy(schema)
