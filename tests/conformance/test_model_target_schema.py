"""Conformance checks for the language-neutral ModelTarget schema."""

import json
from pathlib import Path

from mconet.core.domain import JsonValue, OpenIdentifier
from mconet.testing import (
    SchemaLoader,
    SchemaValidationIssue,
    SchemaValidatorAdapter,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SCHEMA_ROOT = _PROJECT_ROOT / "spec" / "schemas"
_TARGET_SCHEMA_PATH = _SCHEMA_ROOT / "model-target.json"
_DESCRIPTOR_SCHEMA_PATH = _SCHEMA_ROOT / "model-descriptor.json"
_SCHEMA_ID = OpenIdentifier("schema.model_target")


def _load_object(path: Path) -> dict[str, JsonValue]:
    """Load one committed UTF-8 JSON object schema."""
    document: JsonValue = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise AssertionError(f"Schema root must be an object in {path}.")
    return document


def _adapter() -> SchemaValidatorAdapter:
    """Load the target schema through the public schema toolchain."""
    schema = _load_object(_TARGET_SCHEMA_PATH)
    assert schema.get("$id") == _SCHEMA_ID.value
    return SchemaValidatorAdapter(SchemaLoader({_SCHEMA_ID: schema}))


def test_model_target_schema_embeds_the_canonical_model_contract() -> None:
    """Verify the independent target schema cannot drift from model schema."""
    target_schema = _load_object(_TARGET_SCHEMA_PATH)
    descriptor_schema = _load_object(_DESCRIPTOR_SCHEMA_PATH)
    descriptor_schema.pop("$id")
    properties = target_schema.get("properties")
    if not isinstance(properties, dict):
        raise AssertionError("ModelTarget properties must be an object.")

    # The adapter currently has no reference resolver, so the independently
    # loadable target embeds an exact copy of the descriptor contract.
    assert properties.get("model") == descriptor_schema


def test_model_target_schema_accepts_minimal_and_complete_documents() -> None:
    """Verify required target dimensions and optional fields are representable."""
    adapter = _adapter()
    valid_documents: tuple[JsonValue, ...] = (
        {
            "serviceId": "service.local",
            "protocolId": "protocol.native",
            "model": {"name": "model"},
        },
        {
            "serviceId": "service.vendor",
            "protocolId": "protocol.compatible",
            "model": {
                "name": "opaque-model",
                "family": "vendor.future_family",
                "metadata": {"contextWindow": 128_000},
                "extensions": {"futureModelField": True},
            },
            "deploymentId": "production-a",
            "extensions": {"futureRouting": {"region": "east"}},
        },
        {
            "serviceId": "service.local",
            "protocolId": "protocol.native",
            "model": {"name": "model"},
            "deploymentId": None,
        },
    )

    # No target dimension is inferred from another; optional deployment remains
    # independently omitted or explicit null.
    for document in valid_documents:
        assert adapter.validate(_SCHEMA_ID, document) == ()


def test_model_target_schema_rejects_contract_violations_stably() -> None:
    """Verify missing dimensions, invalid IDs, and misplaced fields are precise."""
    adapter = _adapter()
    invalid_documents: tuple[
        tuple[JsonValue, tuple[SchemaValidationIssue, ...]], ...
    ] = (
        (
            {"serviceId": "service.local", "protocolId": "protocol.native"},
            (
                SchemaValidationIssue(
                    "/model", "required", "Required property is missing."
                ),
            ),
        ),
        (
            {
                "serviceId": "Invalid Service",
                "protocolId": "protocol.native",
                "model": {"name": "model"},
            },
            (
                SchemaValidationIssue(
                    "/serviceId", "pattern", "String does not match pattern."
                ),
            ),
        ),
        (
            {
                "serviceId": "service.local",
                "protocolId": "Invalid Protocol",
                "model": {"name": "model"},
            },
            (
                SchemaValidationIssue(
                    "/protocolId", "pattern", "String does not match pattern."
                ),
            ),
        ),
        (
            {
                "serviceId": "service.local",
                "protocolId": "protocol.native",
                "model": {},
            },
            (
                SchemaValidationIssue(
                    "/model/name", "required", "Required property is missing."
                ),
            ),
        ),
        (
            {
                "serviceId": "service.local",
                "protocolId": "protocol.native",
                "model": {"name": "model"},
                "extensions": [],
            },
            (
                SchemaValidationIssue(
                    "/extensions", "type", "Value has an unexpected JSON type."
                ),
            ),
        ),
        (
            {
                "serviceId": "service.local",
                "protocolId": "protocol.native",
                "model": {"name": "model"},
                "endpoint": "https://example.com",
            },
            (
                SchemaValidationIssue(
                    "/endpoint",
                    "additionalProperties",
                    "Additional property is not allowed.",
                ),
            ),
        ),
    )

    # Exact tuples freeze deterministic paths and ensure access fields such as
    # endpoint cannot leak into a model target document.
    for document, expected in invalid_documents:
        assert adapter.validate(_SCHEMA_ID, document) == expected
