"""Behavioral contracts connecting domain values to runtime components."""

from mconet.core.spi.component_descriptor import ComponentDescriptor
from mconet.core.spi.component_type_contract import ComponentTypeContract
from mconet.core.spi.component_type_port import ComponentTypePort
from mconet.core.spi.erased_runtime_value import ErasedRuntimeValue
from mconet.core.spi.runtime_component import RuntimeComponent
from mconet.core.spi.transport_body import TransportBody
from mconet.core.spi.transport_outcome import TransportOutcome
from mconet.core.spi.transport_request import TransportRequest

__all__ = (
    "ComponentDescriptor",
    "ComponentTypeContract",
    "ComponentTypePort",
    "ErasedRuntimeValue",
    "RuntimeComponent",
    "TransportBody",
    "TransportOutcome",
    "TransportRequest",
)
