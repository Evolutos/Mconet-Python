"""Tests for the core-spi public module boundary."""

import mconet.core.spi


def test_core_spi_exports_only_implemented_contracts() -> None:
    """Verify the SPI namespace exposes its implemented public surface."""
    # Keep the explicit export list synchronized without exposing future SPI
    # contracts before their behavior and compatibility rules are implemented.
    assert mconet.core.spi.__all__ == (
        "AuthorizationContext",
        "BodySigningMode",
        "BodySigningRequirement",
        "CapabilityContext",
        "CapabilityRequirement",
        "CapabilityResolution",
        "ComponentDescriptor",
        "ComponentRole",
        "ComponentSelectionResolution",
        "ComponentTypeContract",
        "ComponentTypePort",
        "CredentialSource",
        "CredentialValue",
        "DecoderSelection",
        "EncoderSelection",
        "ErasedRuntimeValue",
        "InteractionCapability",
        "MessageMappingResult",
        "MessageRequestMapper",
        "MessageResponseMapper",
        "ModelIntegrationMatch",
        "ModelIntegrationPlan",
        "ModelTargetMatch",
        "MonitoringEvent",
        "MutableTransportRequest",
        "PayloadDecoder",
        "PayloadEncoder",
        "PlannedComponentSelection",
        "ProtocolExecutionPlan",
        "ProtocolRequestPlan",
        "ResolvedAuthorizationHandler",
        "RuntimeComponent",
        "SatisfiedCapability",
        "SelectedComponent",
        "TaskMatch",
        "TaskProtocolAdapter",
        "Transport",
        "TransportBody",
        "TransportContext",
        "TransportOutcome",
        "TransportRequest",
        "TransportRequestPlan",
        "TransportResponse",
        "TransportResponseMetadata",
        "TransportSelection",
    )
