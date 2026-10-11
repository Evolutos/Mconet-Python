"""Internal immutable exact-key table of model integration bindings."""

from __future__ import annotations

from types import MappingProxyType
from typing import cast

from mconet.core.runtime._integration_type_key import IntegrationTypeKey
from mconet.core.runtime._model_integration_binding import ModelIntegrationBinding
from mconet.core.runtime._model_integration_resolution_errors import (
    ambiguous_model_integration_error,
)


class IntegrationTypeTable:
    """Map each integration type key to exactly one binding.

    The table is assembled once in code by the SDK or a plugin and never
    changes; it has no register, add, or remove operation. Lookup is exact key
    equality, with no prefix, wildcard, or fallback match.
    """

    __slots__ = ("_bindings",)

    def __init__(
        self,
        entries: tuple[tuple[IntegrationTypeKey, ModelIntegrationBinding], ...],
    ) -> None:
        """Build the table from ordered key and binding pairs.

        One binding may appear under several keys, for example for two modes,
        but a key may appear only once.

        Args:
            entries: Pairs of key and binding.

        Raises:
            TypeError: If ``entries`` is not a tuple of key and binding pairs.
            ModelInteractionError: ``ambiguous_model_integration`` when a key
                repeats, even with the same binding, because the table would
                otherwise depend on which pair is read last.
        """
        if not isinstance(cast(object, entries), tuple):
            raise TypeError("IntegrationTypeTable entries must be a tuple.")
        bindings: dict[IntegrationTypeKey, ModelIntegrationBinding] = {}
        for entry in cast(tuple[object, ...], entries):
            key, binding = _validate_entry(entry)
            if key in bindings:
                raise ambiguous_model_integration_error()
            bindings[key] = binding
        # A read-only view of a private dict keeps the table immutable after
        # construction while preserving declaration order for diagnostics.
        self._bindings = MappingProxyType(bindings)

    @property
    def keys(self) -> tuple[IntegrationTypeKey, ...]:
        """Return the keys in declaration order."""
        return tuple(self._bindings)

    def lookup(self, key: IntegrationTypeKey) -> ModelIntegrationBinding | None:
        """Return the binding stored under exactly this key.

        Args:
            key: Key of the request being resolved.

        Returns:
            The unique binding for the key, or ``None`` when there is none.
        """
        return self._bindings.get(key)


def _validate_entry(
    entry: object,
) -> tuple[IntegrationTypeKey, ModelIntegrationBinding]:
    """Return one validated key and binding pair.

    Args:
        entry: One member of the constructor's ``entries`` tuple.

    Returns:
        The pair with its precise types.

    Raises:
        TypeError: If the entry is not a two-item tuple of key and binding.
    """
    if not isinstance(entry, tuple) or len(cast(tuple[object, ...], entry)) != 2:
        raise TypeError("IntegrationTypeTable entries must be key and binding pairs.")
    key, binding = cast(tuple[object, object], entry)
    if not isinstance(key, IntegrationTypeKey):
        raise TypeError("IntegrationTypeTable keys must be IntegrationTypeKey values.")
    if not isinstance(binding, ModelIntegrationBinding):
        raise TypeError(
            "IntegrationTypeTable values must be ModelIntegrationBinding values."
        )
    return key, binding
