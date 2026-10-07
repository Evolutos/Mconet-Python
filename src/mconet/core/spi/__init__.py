"""Behavioral contracts connecting domain values to runtime components."""

from mconet.core.spi.component_descriptor import ComponentDescriptor
from mconet.core.spi.component_type_contract import ComponentTypeContract
from mconet.core.spi.component_type_port import ComponentTypePort

__all__ = ("ComponentDescriptor", "ComponentTypeContract", "ComponentTypePort")
