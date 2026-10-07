"""Immutable descriptive metadata exposed by runtime components."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast

from mconet.core.domain import OpenIdentifier
from mconet.core.spi.component_type_contract import ComponentTypeContract


@dataclass(frozen=True, slots=True)
class ComponentDescriptor:
    """Describe one component without assigning it a registry identity.

    ``name`` and ``version`` are diagnostic labels rather than selection keys.
    ``source`` records the component provenance, the optional type contract
    describes data ports, and capabilities state immutable open feature IDs.
    Components with no data ports may leave ``type_contract`` unspecified.
    """

    name: str
    """Human-readable component name used for diagnostics and monitoring."""

    version: str
    """Component implementation version used for diagnostics and monitoring."""

    source: Literal["builtin", "plugin", "application"]
    """Provenance category for the concrete component instance."""

    type_contract: ComponentTypeContract | None = None
    """Optional immutable input and output port contract."""

    capabilities: frozenset[OpenIdentifier] = frozenset()
    """Immutable open capability identifiers declared by the component."""

    def __post_init__(self) -> None:
        """Require immutable field shapes and one documented source value."""
        name = cast(object, self.name)
        version = cast(object, self.version)
        source = cast(object, self.source)
        type_contract = cast(object, self.type_contract)
        capabilities = cast(object, self.capabilities)

        # Preserve diagnostic text exactly: these labels are observable facts
        # but never normalized into component IDs or used as selection keys.
        if not isinstance(name, str):
            raise TypeError("ComponentDescriptor name must be a string.")
        if not isinstance(version, str):
            raise TypeError("ComponentDescriptor version must be a string.")

        # Source is a closed provenance fact rather than an extensible behavior
        # identifier; reject both non-strings and undocumented categories.
        if not isinstance(source, str):
            raise TypeError("ComponentDescriptor source must be a string.")
        if source not in ("builtin", "plugin", "application"):
            raise ValueError(
                "ComponentDescriptor source must be builtin, plugin, or application."
            )

        # Components without data ports deliberately use None. A present value
        # must be the complete immutable contract rather than a loose mapping.
        if type_contract is not None and not isinstance(
            type_contract, ComponentTypeContract
        ):
            raise TypeError(
                "ComponentDescriptor type_contract must be a "
                "ComponentTypeContract or None."
            )

        # Frozenset prevents capability membership changes after component
        # selection while OpenIdentifier keeps future capability names lossless.
        if not isinstance(capabilities, frozenset):
            raise TypeError("ComponentDescriptor capabilities must be a frozenset.")
        for capability in cast(frozenset[object], capabilities):
            if not isinstance(capability, OpenIdentifier):
                raise TypeError(
                    "ComponentDescriptor capabilities must contain "
                    "OpenIdentifier values."
                )
