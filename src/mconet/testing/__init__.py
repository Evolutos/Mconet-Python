"""Reusable fixtures, test doubles, and contract suites."""

from mconet.testing.fixture_loader import FixtureLoader
from mconet.testing.json_fixture import json_fixtures_equal
from mconet.testing.schema_loader import SchemaLoader
from mconet.testing.schema_validator import (
    SchemaValidationIssue,
    SchemaValidatorAdapter,
)
from mconet.testing.stub_model_integration_resolver import (
    StubModelIntegrationResolver,
)
from mconet.testing.stub_payload_decoder import StubPayloadDecoder
from mconet.testing.stub_payload_encoder import StubPayloadEncoder
from mconet.testing.stub_service_access_resolver import StubServiceAccessResolver
from mconet.testing.stub_task_protocol_adapter import StubTaskProtocolAdapter

__all__ = (
    "FixtureLoader",
    "SchemaLoader",
    "SchemaValidationIssue",
    "SchemaValidatorAdapter",
    "StubModelIntegrationResolver",
    "StubPayloadDecoder",
    "StubPayloadEncoder",
    "StubServiceAccessResolver",
    "StubTaskProtocolAdapter",
    "json_fixtures_equal",
)
