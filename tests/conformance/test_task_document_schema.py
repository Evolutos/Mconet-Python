"""Conformance checks for the recursive TaskDocument schema."""

import json
from pathlib import Path

from mconet.core.domain import JsonValue, OpenIdentifier
from mconet.testing import (
    SchemaLoader,
    SchemaValidationIssue,
    SchemaValidatorAdapter,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SCHEMA_PATH = _PROJECT_ROOT / "spec" / "schemas" / "task-document.json"
_MESSAGE_SCHEMA_PATH = _PROJECT_ROOT / "spec" / "schemas" / "message-document.json"
_SCHEMA_INDEX_PATH = _PROJECT_ROOT / "spec" / "schemas" / "index.json"
_SCHEMA_ID = OpenIdentifier("schema.task_document")
_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"


def _load_object(path: Path) -> dict[str, JsonValue]:
    """Load one committed UTF-8 JSON object document."""
    document: JsonValue = json.loads(path.read_text(encoding="utf-8"))
    # Schemas and their resource index require named root fields; rejecting a
    # scalar here keeps later field assertions explicit and type-safe.
    if not isinstance(document, dict):
        raise AssertionError(f"Expected a JSON object in {path}.")
    return document


def _adapter() -> SchemaValidatorAdapter:
    """Load only the task schema through the public validation toolchain."""
    schema = _load_object(_SCHEMA_PATH)
    # Registering no companion schema proves every reference needed to validate
    # nested messages and task nodes resolves within this committed document.
    assert schema.get("$id") == _SCHEMA_ID.value
    assert schema.get("$schema") == _SCHEMA_DIALECT
    return SchemaValidatorAdapter(SchemaLoader({_SCHEMA_ID: schema}))


def _task_kind(identifier: str, composition: str) -> dict[str, JsonValue]:
    """Create one serialized TaskNode Kind value."""
    # Keeping Kind construction centralized makes composition changes visible
    # in each test without hiding the actual serialized field names.
    return {"id": identifier, "composition": composition}


def _message_kind(
    identifier: str, category: str, composition: str
) -> dict[str, JsonValue]:
    """Create one serialized message element Kind value."""
    # Message kinds carry a category in addition to the task Kind fields, so a
    # separate helper prevents the two independent contracts from being mixed.
    return {"id": identifier, "category": category, "composition": composition}


def _message_document(text: str = "hello") -> dict[str, JsonValue]:
    """Create a minimal MessageDocument containing one user text entry."""
    # A real nested message tree verifies the task schema embeds the complete
    # message contract rather than accepting an untyped placeholder object.
    return {
        "version": "1.0",
        "purpose": "input",
        "root": {
            "id": "messages",
            "kind": _message_kind("message.root", "group", "container"),
            "subElements": [
                {
                    "id": "entry-1",
                    "kind": _message_kind("message.entry", "entry", "leaf"),
                    "subElements": [],
                    "role": {"id": "message.user"},
                    "content": [
                        {
                            "id": "content-1",
                            "kind": {"id": "content.text"},
                            "text": text,
                        }
                    ],
                }
            ],
        },
    }


def _root(children: list[JsonValue] | None = None) -> dict[str, JsonValue]:
    """Create the serialized task root with an ordered child collection."""
    # Allocate a fresh list for the empty case so callers cannot accidentally
    # share and mutate state between otherwise independent test documents.
    return {
        "id": "task-root",
        "kind": _task_kind("task.root", "container"),
        "children": [] if children is None else children,
    }


def test_task_document_schema_is_registered_and_domain_scoped() -> None:
    """Verify stable discovery and the exact document-level field boundary."""
    schema = _load_object(_SCHEMA_PATH)
    index = _load_object(_SCHEMA_INDEX_PATH)
    properties = schema.get("properties")
    resources = index.get("resources")
    if not isinstance(properties, dict) or not isinstance(resources, list):
        raise AssertionError("Schema properties and index resources must be objects.")

    # TaskDocument owns its tree envelope only. Model routing, service access,
    # and request projection fields belong to adjacent contracts.
    assert "task-document.json" in resources
    assert frozenset(properties) == frozenset(
        ("extensions", "metadata", "root", "version")
    )
    for unrelated_name in (
        "artifacts",
        "descriptor",
        "messages",
        "parameters",
        "protocol",
        "serviceAccess",
        "target",
        "temperature",
        "transport",
    ):
        assert unrelated_name not in properties


def test_task_document_schema_embeds_the_canonical_message_contract() -> None:
    """Verify the independently loadable task schema cannot drift from messages."""
    task_schema = _load_object(_SCHEMA_PATH)
    message_schema = _load_object(_MESSAGE_SCHEMA_PATH)
    task_definitions = task_schema.get("$defs")
    message_definitions = message_schema.pop("$defs", None)
    message_schema.pop("$id", None)
    message_schema.pop("$schema", None)
    if not isinstance(task_definitions, dict) or not isinstance(
        message_definitions, dict
    ):
        raise AssertionError("Both schemas must expose object definitions.")

    # The task schema uses namespaced aliases where message definition names
    # would be ambiguous beside task definitions. Rewriting only local reference
    # text creates the exact canonical shape expected in the standalone schema.
    replacements = {
        "#/$defs/relation": "#/$defs/messageRelation",
        "#/$defs/rootGroup": "#/$defs/messageRootGroup",
    }

    def namespaced(value: JsonValue) -> JsonValue:
        """Copy JSON data while namespacing message-local reference strings."""
        # A JSON round trip provides a detached tree with only supported JSON
        # values, then exact string replacement leaves ordinary content intact.
        serialized = json.dumps(value, ensure_ascii=False, sort_keys=True)
        for source, target in replacements.items():
            serialized = serialized.replace(source, target)
        return json.loads(serialized)

    # The embedded document boundary and every supporting definition must remain
    # byte-shape equivalent after the two intentional reference-name aliases.
    assert task_definitions.get("messageDocument") == namespaced(message_schema)
    for name, definition in message_definitions.items():
        target_name = {
            "relation": "messageRelation",
            "rootGroup": "messageRootGroup",
        }.get(name, name)
        assert task_definitions.get(target_name) == namespaced(definition)


def test_task_document_schema_accepts_minimal_and_complete_trees() -> None:
    """Verify concrete nodes and recursive open nodes compose in one document."""
    adapter = _adapter()
    minimal: JsonValue = {"version": "1.0", "root": _root()}
    complete: JsonValue = {
        "version": "future-version",
        "root": _root(
            [
                {
                    "id": "input",
                    "kind": _task_kind("task.input", "leaf"),
                    "children": [],
                    "messages": _message_document("你好\nworld 👋"),
                    "relations": [
                        {
                            "source": "input",
                            "target": "configuration",
                            "type": "task.precedes",
                            "metadata": {"order": 1},
                        }
                    ],
                    "metadata": {"source": "conversation"},
                    "extensions": {"vendor.trace": True},
                },
                {
                    "id": "configuration",
                    "kind": _task_kind("task.configuration", "leaf"),
                    "children": [],
                    "parameters": {
                        "temperature": 0.25,
                        "topP": 0.9,
                        "maxOutputTokens": 1024,
                        "stop": ["END"],
                        "seed": 7,
                    },
                },
                {
                    "id": "vendor-pipeline",
                    "kind": _task_kind("vendor.pipeline", "container"),
                    "children": [
                        {
                            "id": "vendor-step",
                            "kind": _task_kind("vendor.step", "leaf"),
                            "children": [],
                            "providerPayload": {"mode": "future"},
                        }
                    ],
                    "providerPolicy": {"retries": 2},
                },
            ]
        ),
        "metadata": {"request": "example"},
        "extensions": {"vendor.request": {"enabled": True}},
    }

    # The minimal case fixes the empty-tree boundary. The complete case walks
    # supported leaves, embedded messages, all generation settings, relations,
    # recursive open nodes, and provider-owned payload preservation.
    assert adapter.validate(_SCHEMA_ID, minimal) == ()
    assert adapter.validate(_SCHEMA_ID, complete) == ()


def test_task_document_schema_accepts_deep_recursive_open_containers() -> None:
    """Verify repeated local references consume deeply nested task children."""
    node: dict[str, JsonValue] = {
        "id": "leaf",
        "kind": _task_kind("vendor.leaf", "leaf"),
        "children": [],
        "payload": {"opaque": True},
    }
    for index in range(20):
        # Each wrapper consumes one child level before following taskNode again,
        # distinguishing supported recursion from a non-consuming reference loop.
        node = {
            "id": f"container-{index}",
            "kind": _task_kind("vendor.container", "container"),
            "children": [node],
        }
    document: JsonValue = {"version": "1.0", "root": _root([node])}

    # Twenty levels are enough to exercise recursive resolution without making
    # the test sensitive to implementation recursion limits.
    assert _adapter().validate(_SCHEMA_ID, document) == ()


def test_task_document_schema_rejects_document_boundary_violations() -> None:
    """Verify required fields, root classification, and field ownership fail."""
    adapter = _adapter()
    invalid_documents: tuple[
        tuple[JsonValue, tuple[SchemaValidationIssue, ...]], ...
    ] = (
        (
            {"version": "1.0"},
            (
                SchemaValidationIssue(
                    "/root", "required", "Required property is missing."
                ),
            ),
        ),
        (
            {"version": "   ", "root": _root()},
            (
                SchemaValidationIssue(
                    "/version", "pattern", "String does not match pattern."
                ),
            ),
        ),
        (
            {
                "version": "1.0",
                "root": {
                    "id": "task-root",
                    "kind": _task_kind("vendor.root", "container"),
                    "children": [],
                },
            },
            (
                SchemaValidationIssue(
                    "/root/kind/id", "const", "Value does not match const."
                ),
            ),
        ),
        (
            {"version": "1.0", "root": _root(), "target": {}},
            (
                SchemaValidationIssue(
                    "/target",
                    "additionalProperties",
                    "Additional property is not allowed.",
                ),
            ),
        ),
    )

    # Exact issue tuples freeze deterministic paths and ensure request routing
    # cannot be smuggled into the task document envelope.
    for document, expected in invalid_documents:
        assert adapter.validate(_SCHEMA_ID, document) == expected


def test_task_document_schema_rejects_malformed_supported_nodes() -> None:
    """Verify known task kinds cannot fall through permissive open branches."""
    adapter = _adapter()
    invalid_nodes: tuple[JsonValue, ...] = (
        {
            "id": "input",
            "kind": _task_kind("task.input", "leaf"),
            "children": [],
        },
        {
            "id": "input",
            "kind": _task_kind("task.input", "leaf"),
            "children": [],
            "messages": {"version": "1.0", "purpose": "input"},
        },
        {
            "id": "configuration",
            "kind": _task_kind("task.configuration", "leaf"),
            "children": [],
        },
        {
            "id": "configuration",
            "kind": _task_kind("task.configuration", "leaf"),
            "children": [],
            "parameters": {"topP": 1.1},
        },
        {
            "id": "configuration",
            "kind": _task_kind("task.configuration", "leaf"),
            "children": [
                {
                    "id": "child",
                    "kind": _task_kind("vendor.child", "leaf"),
                    "children": [],
                }
            ],
            "parameters": {},
        },
        {
            "id": "input-container",
            "kind": _task_kind("task.input", "container"),
            "children": [],
        },
        {
            "id": "nested-root",
            "kind": _task_kind("task.root", "leaf"),
            "children": [],
        },
    )
    expected = (
        SchemaValidationIssue(
            "/root/children/0",
            "oneOf",
            "Value must match exactly one schema alternative.",
        ),
    )

    # Open branches deliberately exclude every standard ID. Therefore missing
    # payloads, invalid nested documents, bad bounds, wrong composition, and a
    # nested root all fail instead of becoming provider-defined nodes.
    for node in invalid_nodes:
        document: JsonValue = {"version": "1.0", "root": _root([node])}
        assert adapter.validate(_SCHEMA_ID, document) == expected


def test_task_document_schema_leaves_graph_invariants_to_domain_validation() -> None:
    """Verify schema validation preserves graph evidence for domain validators."""
    document: JsonValue = {
        "version": "1.0",
        "root": _root(
            [
                {
                    "id": "duplicate",
                    "kind": _task_kind("vendor.first", "leaf"),
                    "children": [],
                    "relations": [
                        {
                            "source": "duplicate",
                            "target": "missing",
                            "type": "task.references",
                        }
                    ],
                },
                {
                    "id": "duplicate",
                    "kind": _task_kind("vendor.second", "leaf"),
                    "children": [],
                },
            ]
        ),
    }

    # Portable JSON Schema covers local shape but cannot express global ID
    # uniqueness or relation endpoint resolution. Keeping this document valid
    # ensures those checks remain the TaskDocument validator's responsibility.
    assert _adapter().validate(_SCHEMA_ID, document) == ()
