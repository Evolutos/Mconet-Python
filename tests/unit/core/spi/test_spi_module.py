"""Tests for the core-spi public module boundary."""

import mconet.core.spi


def test_core_spi_exports_only_implemented_contracts() -> None:
    """Verify the SPI namespace exposes its implemented public surface."""
    # Keep the explicit export list synchronized without exposing future SPI
    # contracts before their behavior and compatibility rules are implemented.
    assert mconet.core.spi.__all__ == (
        "BodySigningMode",
        "BodySigningRequirement",
        "CapabilityRequirement",
        "CapabilityResolution",
        "ComponentDescriptor",
        "ComponentRole",
        "ComponentSelectionResolution",
        "ComponentTypeContract",
        "ComponentTypePort",
        "DecoderSelection",
        "EncoderSelection",
        "ErasedRuntimeValue",
        "InteractionCapability",
        "ModelIntegrationMatch",
        "ModelIntegrationPlan",
        "ModelTargetMatch",
        "MutableTransportRequest",
        "PlannedComponentSelection",
        "ProtocolExecutionPlan",
        "ProtocolRequestPlan",
        "RuntimeComponent",
        "SatisfiedCapability",
        "SelectedComponent",
        "TaskMatch",
        "TransportBody",
        "TransportContext",
        "TransportOutcome",
        "TransportRequest",
        "TransportRequestPlan",
        "TransportResponse",
        "TransportResponseMetadata",
        "TransportSelection",
    )
