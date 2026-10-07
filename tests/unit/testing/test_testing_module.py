"""Tests for the testing module boundary."""

import mconet.testing


def test_testing_module_imports_without_public_utilities() -> None:
    """Verify the testing module exports only completed public utilities."""
    assert mconet.testing.__all__ == (
        "AdapterContractSuite",
        "AuthorizationHandlerResolverContractSuite",
        "ComponentCallRecorder",
        "ControllableCancellationSignal",
        "DeterministicIdGenerator",
        "ErrorPayloadDecoderContractSuite",
        "FakeClock",
        "FaultInjectionHarness",
        "FixtureLoader",
        "MockTransport",
        "PayloadEncoderContractSuite",
        "RecordingTransport",
        "SchemaLoader",
        "SchemaValidationIssue",
        "SchemaValidatorAdapter",
        "SecretScanner",
        "SnapshotComparator",
        "StubAuthorizationHandler",
        "StubAuthorizationHandlerResolver",
        "StubInteractionMonitor",
        "StubModelIntegrationResolver",
        "StubPayloadDecoder",
        "StubPayloadEncoder",
        "StubServiceAccessResolver",
        "StubTaskProtocolAdapter",
        "SuccessPayloadDecoderContractSuite",
        "TransportContractSuite",
        "json_fixtures_equal",
    )
