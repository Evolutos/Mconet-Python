"""Reusable fixtures, test doubles, and contract suites."""

from mconet.testing.fixture_loader import FixtureLoader
from mconet.testing.json_fixture import json_fixtures_equal
from mconet.testing.schema_loader import SchemaLoader
from mconet.testing.schema_validator import (
    SchemaValidationIssue,
    SchemaValidatorAdapter,
)
from mconet.testing.stub_task_protocol_adapter import StubTaskProtocolAdapter

__all__ = (
    "FixtureLoader",
    "SchemaLoader",
    "SchemaValidationIssue",
    "SchemaValidatorAdapter",
    "StubTaskProtocolAdapter",
    "json_fixtures_equal",
)
