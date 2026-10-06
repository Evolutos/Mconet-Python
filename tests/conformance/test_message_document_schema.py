"""Conformance checks for the recursive MessageDocument schema."""

import json
from pathlib import Path

from mconet.core.domain import JsonValue, OpenIdentifier
from mconet.testing import (
    SchemaLoader,
    SchemaValidationIssue,
    SchemaValidatorAdapter,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SCHEMA_PATH = _PROJECT_ROOT / "spec" / "schemas" / "message-document.json"
_SCHEMA_INDEX_PATH = _PROJECT_ROOT / "spec" / "schemas" / "index.json"
_SCHEMA_ID = OpenIdentifier("schema.message_document")
_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"


def _load_object(path: Path) -> dict[str, JsonValue]:
    """Load one committed UTF-8 JSON object document."""
    document: JsonValue = json.loads(path.read_text(encoding="utf-8"))
    # Schema and index roots must be objects so stable named fields can be
    # inspected without accepting an unrelated scalar or array resource.
    if not isinstance(document, dict):
        raise AssertionError(f"Expected a JSON object in {path}.")
    return document


def _adapter() -> SchemaValidatorAdapter:
    """Load the committed message schema through the public toolchain."""
    schema = _load_object(_SCHEMA_PATH)
    # The resource ID is checked independently from registration so lookup and
    # committed schema identity or reference-sibling dialect cannot drift.
    assert schema.get("$id") == _SCHEMA_ID.value
    assert schema.get("$schema") == _SCHEMA_DIALECT
    return SchemaValidatorAdapter(SchemaLoader({_SCHEMA_ID: schema}))


def _kind(identifier: str, category: str, composition: str) -> dict[str, JsonValue]:
    """Create one serialized open message element Kind."""
    # Explicit fields keep test documents readable while exercising the complete
    # Kind object shape required by every recursive element branch.
    return {"id": identifier, "category": category, "composition": composition}


def _minimal_root() -> dict[str, JsonValue]:
    """Create the smallest valid serialized root group."""
    # An empty ordered child list is a real value rather than an omitted tree;
    # metadata, relations, and extensions remain optional default channels.
    return {
        "id": "root",
        "kind": _kind("message.root", "group", "container"),
        "subElements": [],
    }


def test_message_document_schema_is_registered_and_domain_scoped() -> None:
    """Verify stable discovery and an exact document-level field boundary."""
    schema = _load_object(_SCHEMA_PATH)
    index = _load_object(_SCHEMA_INDEX_PATH)
    properties = schema.get("properties")
    resources = index.get("resources")
    if not isinstance(properties, dict) or not isinstance(resources, list):
        raise AssertionError("Schema properties and index resources must be arrays.")

    # The schema remains independently discoverable and exposes only message
    # document fields, excluding task configuration, access, and protocol data.
    assert "message-document.json" in resources
    assert frozenset(properties) == frozenset(
        ("extensions", "metadata", "purpose", "root", "version")
    )
    for unrelated_name in (
        "artifacts",
        "authorization",
        "endpoint",
        "generationParameters",
        "payload",
        "protocol",
        "temperature",
        "tools",
        "transport",
    ):
        assert unrelated_name not in properties


def test_message_document_schema_accepts_minimal_and_complete_trees() -> None:
    """Verify empty roots and recursive concrete/open elements are representable."""
    adapter = _adapter()
    minimal: JsonValue = {
        "version": "1.0",
        "purpose": "input",
        "root": _minimal_root(),
    }
    complete: JsonValue = {
        "version": "future-version",
        "purpose": "context",
        "root": {
            "id": "root",
            "kind": _kind("message.root", "group", "container"),
            "name": "Conversation",
            "attributes": {"locale": "zh-CN"},
            "value": None,
            "subElements": [
                {
                    "id": "history",
                    "kind": _kind("message.history", "group", "container"),
                    "subElements": [
                        {
                            "id": "entry-1",
                            "kind": _kind("message.entry", "entry", "leaf"),
                            "name": None,
                            "attributes": {},
                            "value": None,
                            "subElements": [],
                            "role": {
                                "id": "message.user",
                                "semantic": "User input",
                                "rawValue": "user",
                                "extensions": {"vendor.role": "customer"},
                            },
                            "content": [
                                {
                                    "id": "content-1",
                                    "kind": {"id": "content.text"},
                                    "text": "你好\n世界 👋",
                                    "metadata": {"language": "zh-CN"},
                                    "extensions": {"vendor.style": "plain"},
                                },
                                {
                                    "id": "content-2",
                                    "kind": {"id": "vendor.rich_text"},
                                    "metadata": {"format": "portable"},
                                    "extensions": {"vendor.raw": {"runs": 1}},
                                },
                            ],
                            "relations": [
                                {
                                    "source": "entry-1",
                                    "target": "note-1",
                                    "type": "message.references",
                                    "metadata": {"confidence": 1.0},
                                }
                            ],
                            "metadata": {"turn": 1},
                            "extensions": {"vendor.entry": True},
                        }
                    ],
                },
                {
                    "id": "note-1",
                    "kind": _kind("vendor.note", "note", "leaf"),
                    "name": "annotation",
                    "attributes": {"priority": 1},
                    "value": {"text": "portable"},
                    "subElements": [],
                    "relations": [],
                    "metadata": {},
                    "extensions": {"vendor.note": True},
                },
            ],
            "relations": [],
            "metadata": {"tree": "complete"},
            "extensions": {"vendor.root": True},
        },
        "metadata": {"conversation": "example"},
        "extensions": {"vendor.trace": {"enabled": True}},
    }

    # The first case proves empty ordered trees are explicit. The second walks
    # nested containers, a concrete Entry, text/open content, an open leaf, and
    # relations through one recursively loaded schema document.
    assert adapter.validate(_SCHEMA_ID, minimal) == ()
    assert adapter.validate(_SCHEMA_ID, complete) == ()


def test_message_document_schema_accepts_deep_recursive_containers() -> None:
    """Verify local references repeatedly validate nested element arrays."""
    element: dict[str, JsonValue] = {
        "id": "leaf",
        "kind": _kind("vendor.leaf", "leaf", "leaf"),
        "subElements": [],
    }
    for index in range(20):
        # Each new object consumes one instance level before the same local
        # messageElement reference is evaluated again for its child.
        element = {
            "id": f"container-{index}",
            "kind": _kind("vendor.container", "group", "container"),
            "subElements": [element],
        }
    document: JsonValue = {
        "version": "1.0",
        "purpose": "custom",
        "root": {
            "id": "root",
            "kind": _kind("message.root", "group", "container"),
            "subElements": [element],
        },
    }

    # Repeated validation proves $ref is genuinely recursive rather than an
    # inert annotation that checks only one embedded tree level.
    assert _adapter().validate(_SCHEMA_ID, document) == ()


def test_message_document_schema_rejects_document_boundary_violations() -> None:
    """Verify required fields, purpose, root Kind, and unrelated fields fail."""
    adapter = _adapter()
    invalid_documents: tuple[
        tuple[JsonValue, tuple[SchemaValidationIssue, ...]], ...
    ] = (
        (
            {"version": "1.0", "purpose": "input"},
            (
                SchemaValidationIssue(
                    "/root", "required", "Required property is missing."
                ),
            ),
        ),
        (
            {"version": "1.0", "purpose": "vendor", "root": _minimal_root()},
            (
                SchemaValidationIssue(
                    "/purpose", "enum", "Value is not an allowed enum member."
                ),
            ),
        ),
        (
            {"version": "   ", "purpose": "input", "root": _minimal_root()},
            (
                SchemaValidationIssue(
                    "/version", "pattern", "String does not match pattern."
                ),
            ),
        ),
        (
            {
                "version": "1.0",
                "purpose": "input",
                "root": {
                    "id": "root",
                    "kind": _kind("message.history", "group", "container"),
                    "subElements": [],
                },
            },
            (
                SchemaValidationIssue(
                    "/root/kind/id", "const", "Value does not match const."
                ),
            ),
        ),
        (
            {
                "version": "1.0",
                "purpose": "input",
                "root": _minimal_root(),
                "temperature": 0.5,
            },
            (
                SchemaValidationIssue(
                    "/temperature",
                    "additionalProperties",
                    "Additional property is not allowed.",
                ),
            ),
        ),
    )

    # Exact issue tuples freeze deterministic paths and prevent task or protocol
    # concerns from being accepted at the MessageDocument boundary.
    for document, expected in invalid_documents:
        assert adapter.validate(_SCHEMA_ID, document) == expected


def test_message_document_schema_rejects_invalid_recursive_elements() -> None:
    """Verify leaf, entry content, and nested shape rules apply at every depth."""
    adapter = _adapter()

    def _document_with(element: JsonValue) -> JsonValue:
        """Place one caller-selected child below an otherwise valid root."""
        # A stable wrapper isolates element-branch failures from document root,
        # version, and purpose validation in every negative scenario.
        return {
            "version": "1.0",
            "purpose": "input",
            "root": {
                "id": "root",
                "kind": _kind("message.root", "group", "container"),
                "subElements": [element],
            },
        }

    invalid_elements: tuple[JsonValue, ...] = (
        {
            "id": "entry-1",
            "kind": _kind("message.entry", "entry", "leaf"),
            "subElements": [],
            "role": {"id": "message.user"},
            "content": [],
        },
        {
            "id": "entry-1",
            "kind": _kind("message.entry", "entry", "leaf"),
            "subElements": [],
            "role": {"id": "message.user"},
            "content": [{"id": "content-1", "kind": {"id": "content.text"}}],
        },
        {
            "id": "leaf",
            "kind": _kind("vendor.note", "note", "leaf"),
            "subElements": [
                {
                    "id": "child",
                    "kind": _kind("vendor.child", "note", "leaf"),
                    "subElements": [],
                }
            ],
        },
        {
            "id": "container",
            "kind": _kind("vendor.group", "group", "container"),
        },
    )
    expected = (
        SchemaValidationIssue(
            "/root/subElements/0",
            "oneOf",
            "Value must match exactly one schema alternative.",
        ),
    )

    # Branch diagnostics intentionally collapse to one stable oneOf issue at the
    # invalid element, independent of how many alternatives rejected its shape.
    for element in invalid_elements:
        assert adapter.validate(_SCHEMA_ID, _document_with(element)) == expected
