"""Behavioral contracts connecting domain values to runtime components."""

from mconet.core.spi.component_descriptor import ComponentDescriptor
from mconet.core.spi.component_role import ComponentRole
from mconet.core.spi.component_selection_resolution import (
    ComponentSelectionResolution,
)
from mconet.core.spi.component_type_contract import ComponentTypeContract
from mconet.core.spi.component_type_port import ComponentTypePort
from mconet.core.spi.decoder_selection import DecoderSelection
from mconet.core.spi.encoder_selection import EncoderSelection
from mconet.core.spi.erased_runtime_value import ErasedRuntimeValue
from mconet.core.spi.planned_component_selection import PlannedComponentSelection
from mconet.core.spi.runtime_component import RuntimeComponent
from mconet.core.spi.selected_component import SelectedComponent
from mconet.core.spi.transport_body import TransportBody
from mconet.core.spi.transport_context import TransportContext
from mconet.core.spi.transport_outcome import TransportOutcome
from mconet.core.spi.transport_request import TransportRequest
from mconet.core.spi.transport_response import TransportResponse
from mconet.core.spi.transport_response_metadata import TransportResponseMetadata
from mconet.core.spi.transport_selection import TransportSelection

__all__ = (
    "ComponentDescriptor",
    "ComponentRole",
    "ComponentSelectionResolution",
    "ComponentTypeContract",
    "ComponentTypePort",
    "DecoderSelection",
    "EncoderSelection",
    "ErasedRuntimeValue",
    "PlannedComponentSelection",
    "RuntimeComponent",
    "SelectedComponent",
    "TransportBody",
    "TransportContext",
    "TransportOutcome",
    "TransportRequest",
    "TransportResponse",
    "TransportResponseMetadata",
    "TransportSelection",
)
