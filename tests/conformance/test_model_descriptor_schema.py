"""Conformance checks for the language-neutral ModelDescriptor schema."""

import json
from pathlib import Path

from mconet.core.domain import JsonValue, OpenIdentifier
from mconet.testing import (
    SchemaLoader,
    SchemaValidationIssue,
    SchemaValidatorAdapter,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SCHEMA_PATH = _PROJECT_ROOT / "spec" / "schemas" / "model-descriptor.json"
_SCHEMA_ID = OpenIdentifier("schema.model_descriptor")


def _adapter() -> SchemaValidatorAdapter:
    """Load the committed schema through the public schema toolchain."""
    document: JsonValue = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise AssertionError("ModelDescriptor schema root must be an object.")
    # The resource identifier is the stable lookup key and must remain aligned
    # with the independently selected conformance identifier.
    assert document.get("$id") == _SCHEMA_ID.value
    return SchemaValidatorAdapter(SchemaLoader({_SCHEMA_ID: document}))


def test_model_descriptor_schema_accepts_minimal_and_complete_documents() -> None:
    """Verify only name is required while every declared optional field works."""
    adapter = _adapter()
    valid_documents: tuple[JsonValue, ...] = (
        {"name": "provider/model"},
        {"name": "provider\nmodel"},
        {
            "name": "opaque-2026-name",
            "displayName": "Display Name",
            "family": "vendor.future_family",
            "version": "2026-10",
            "description": "Description",
            "metadata": {"contextWindow": 128_000},
            "extensions": {"futureField": {"enabled": True}},
        },
        {
            "name": "model",
            "displayName": None,
            "family": None,
            "version": None,
            "description": None,
        },
    )

    # Optional fields may be omitted or explicit null according to the shared
    # Optional serialization rules; no field is inferred from name.
    for document in valid_documents:
        assert adapter.validate(_SCHEMA_ID, document) == ()


def test_model_descriptor_schema_rejects_contract_violations_stably() -> None:
    """Verify required, syntax, mapping, and unknown-field failures are precise."""
    adapter = _adapter()
    invalid_documents: tuple[
        tuple[JsonValue, tuple[SchemaValidationIssue, ...]], ...
    ] = (
        (
            {},
            (
                SchemaValidationIssue(
                    "/name", "required", "Required property is missing."
                ),
            ),
        ),
        (
            {"name": "   "},
            (
                SchemaValidationIssue(
                    "/name", "pattern", "String does not match pattern."
                ),
            ),
        ),
        (
            {"name": "model", "family": "Invalid Family"},
            (
                SchemaValidationIssue(
                    "/family", "pattern", "String does not match pattern."
                ),
            ),
        ),
        (
            {"name": "model", "metadata": []},
            (
                SchemaValidationIssue(
                    "/metadata", "type", "Value has an unexpected JSON type."
                ),
            ),
        ),
        (
            {"name": "model", "futureField": True},
            (
                SchemaValidationIssue(
                    "/futureField",
                    "additionalProperties",
                    "Additional property is not allowed.",
                ),
            ),
        ),
    )

    # Exact issue tuples freeze cross-language paths, keywords, messages, and
    # deterministic ordering for each independent invalid document.
    for document, expected in invalid_documents:
        assert adapter.validate(_SCHEMA_ID, document) == expected
