"""Tests for the testing module boundary."""

import mconet.testing


def test_testing_module_imports_without_public_utilities() -> None:
    """Verify the testing module exports only completed public utilities."""
    assert mconet.testing.__all__ == (
        "FakeClock",
        "FixtureLoader",
        "MockTransport",
        "RecordingTransport",
        "SchemaLoader",
        "SchemaValidationIssue",
        "SchemaValidatorAdapter",
        "StubAuthorizationHandler",
        "StubAuthorizationHandlerResolver",
        "StubInteractionMonitor",
        "StubModelIntegrationResolver",
        "StubPayloadDecoder",
        "StubPayloadEncoder",
        "StubServiceAccessResolver",
        "StubTaskProtocolAdapter",
        "json_fixtures_equal",
    )
