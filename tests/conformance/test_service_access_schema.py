"""Conformance checks for the non-sensitive ServiceAccess schema."""

import json
from pathlib import Path

from mconet.core.domain import JsonValue, OpenIdentifier
from mconet.testing import (
    SchemaLoader,
    SchemaValidationIssue,
    SchemaValidatorAdapter,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SCHEMA_PATH = _PROJECT_ROOT / "spec" / "schemas" / "service-access.json"
_SCHEMA_ID = OpenIdentifier("schema.service_access")


def _load_schema() -> dict[str, JsonValue]:
    """Load the committed UTF-8 ServiceAccess schema object."""
    document: JsonValue = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    # A schema must remain an object so the public loader receives the exact
    # mapping shape supported by every language implementation.
    if not isinstance(document, dict):
        raise AssertionError("ServiceAccess schema root must be an object.")
    return document


def _adapter() -> SchemaValidatorAdapter:
    """Load the schema through the public deterministic validation toolchain."""
    schema = _load_schema()
    # Keep the committed resource identifier synchronized with the stable ID
    # selected independently by conformance callers.
    assert schema.get("$id") == _SCHEMA_ID.value
    return SchemaValidatorAdapter(SchemaLoader({_SCHEMA_ID: schema}))


def test_service_access_schema_contains_only_non_sensitive_properties() -> None:
    """Verify authorization and credential fields cannot enter ordinary schema."""
    schema = _load_schema()
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        raise AssertionError("ServiceAccess properties must be an object.")

    # The allowlist is exact: authorization remains an opaque runtime component,
    # and no convenience apiKey/token field can become persistent payload data.
    assert frozenset(properties) == frozenset(
        (
            "apiVersion",
            "endpoint",
            "extensions",
            "headers",
            "projectId",
            "query",
            "tenantId",
        )
    )
    assert "authorization" not in properties


def test_service_access_schema_accepts_minimal_and_complete_documents() -> None:
    """Verify optional input and complete non-sensitive context are representable."""
    adapter = _adapter()
    valid_documents: tuple[JsonValue, ...] = (
        {},
        {
            "endpoint": "https://models.example.test/v1",
            "headers": {
                "values": [
                    {"name": "X-Feature", "value": "first"},
                    {"name": "x-feature", "value": "second"},
                ]
            },
            "query": {
                "values": [
                    {"name": "tag", "value": "first"},
                    {"name": "tag", "value": "second"},
                ]
            },
            "apiVersion": "2026-10-01",
            "projectId": "project-a",
            "tenantId": "tenant-a",
            "extensions": {"futureAccessOption": True},
        },
        {
            "endpoint": None,
            "headers": {"values": []},
            "query": {"values": []},
            "apiVersion": None,
            "projectId": None,
            "tenantId": None,
        },
        {"endpoint": "vendor+rpc://models.example.test"},
    )

    # Omitted fields preserve unresolved/default semantics; arrays retain every
    # repeated Header or Query entry and custom absolute schemes stay open.
    for document in valid_documents:
        assert adapter.validate(_SCHEMA_ID, document) == ()


def test_service_access_schema_rejects_contract_violations_stably() -> None:
    """Verify sensitive, malformed, and misplaced fields produce exact issues."""
    adapter = _adapter()
    invalid_documents: tuple[
        tuple[JsonValue, tuple[SchemaValidationIssue, ...]], ...
    ] = (
        (
            {"authorization": {"kind": "authorization.bearer"}},
            (
                SchemaValidationIssue(
                    "/authorization",
                    "additionalProperties",
                    "Additional property is not allowed.",
                ),
            ),
        ),
        (
            {"apiKey": True},
            (
                SchemaValidationIssue(
                    "/apiKey",
                    "additionalProperties",
                    "Additional property is not allowed.",
                ),
            ),
        ),
        (
            {"endpoint": "relative/path"},
            (
                SchemaValidationIssue(
                    "/endpoint", "pattern", "String does not match pattern."
                ),
            ),
        ),
        (
            {"endpoint": "https://models.example.test/invalid path"},
            (
                SchemaValidationIssue(
                    "/endpoint", "pattern", "String does not match pattern."
                ),
            ),
        ),
        (
            {"endpoint": "https://models.example.test/path\n"},
            (
                SchemaValidationIssue(
                    "/endpoint", "pattern", "String does not match pattern."
                ),
            ),
        ),
        (
            {"headers": []},
            (
                SchemaValidationIssue(
                    "/headers", "type", "Value has an unexpected JSON type."
                ),
            ),
        ),
        (
            {"headers": {}},
            (
                SchemaValidationIssue(
                    "/headers/values", "required", "Required property is missing."
                ),
            ),
        ),
        (
            {"headers": {"values": [{"name": "Invalid Header", "value": "v"}]}},
            (
                SchemaValidationIssue(
                    "/headers/values/0/name",
                    "pattern",
                    "String does not match pattern.",
                ),
            ),
        ),
        (
            {"headers": {"values": [{"name": "X-Value", "value": "line\nvalue"}]}},
            (
                SchemaValidationIssue(
                    "/headers/values/0/value",
                    "pattern",
                    "String does not match pattern.",
                ),
            ),
        ),
        (
            {"headers": {"values": [{"name": "X-Value", "value": "line\n"}]}},
            (
                SchemaValidationIssue(
                    "/headers/values/0/value",
                    "pattern",
                    "String does not match pattern.",
                ),
            ),
        ),
        (
            {"query": {"values": [{"name": "tag"}]}},
            (
                SchemaValidationIssue(
                    "/query/values/0/value",
                    "required",
                    "Required property is missing.",
                ),
            ),
        ),
        (
            {"apiVersion": 1},
            (
                SchemaValidationIssue(
                    "/apiVersion", "type", "Value has an unexpected JSON type."
                ),
            ),
        ),
    )

    # Exact tuples freeze JSON Pointer paths and deterministic keyword messages,
    # including explicit rejection of runtime authorization and secret fields.
    for document, expected in invalid_documents:
        assert adapter.validate(_SCHEMA_ID, document) == expected
