"""Conformance checks for the standalone ModelRequest schema."""

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
_SCHEMA_PATH = _SCHEMA_ROOT / "model-request.json"
_SCHEMA_INDEX_PATH = _SCHEMA_ROOT / "index.json"
_TARGET_SCHEMA_PATH = _SCHEMA_ROOT / "model-target.json"
_ACCESS_SCHEMA_PATH = _SCHEMA_ROOT / "service-access.json"
_TASK_SCHEMA_PATH = _SCHEMA_ROOT / "task-document.json"
_CATALOG_SCHEMA_PATH = _SCHEMA_ROOT / "artifact-catalog.json"
_SCHEMA_ID = OpenIdentifier("schema.model_request")
_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"


def _load_object(path: Path) -> dict[str, JsonValue]:
    """Load one committed UTF-8 JSON object document."""
    document: JsonValue = json.loads(path.read_text(encoding="utf-8"))
    # Every schema and collection index used here requires named fields; reject
    # unrelated scalar or array resources before inspecting contract members.
    if not isinstance(document, dict):
        raise AssertionError(f"Expected a JSON object in {path}.")
    return document


def _embedded_root(schema: dict[str, JsonValue]) -> dict[str, JsonValue]:
    """Return a detached schema root without resource identity or definitions."""
    # Resource identity belongs only to the independently addressable source.
    # A shallow copy is sufficient because membership alone is changed here.
    embedded = dict(schema)
    embedded.pop("$defs", None)
    embedded.pop("$id", None)
    embedded.pop("$schema", None)
    return embedded


def _definitions(schema: dict[str, JsonValue]) -> dict[str, JsonValue]:
    """Return one schema's object-valued local definition map."""
    definitions = schema.get("$defs")
    # Definition parity needs named members. Treat a missing or non-object map as
    # a malformed committed schema instead of silently comparing an empty value.
    if not isinstance(definitions, dict):
        raise AssertionError("Schema definitions must be an object.")
    return definitions


def _adapter() -> SchemaValidatorAdapter:
    """Load only the request schema through the public validation toolchain."""
    schema = _load_object(_SCHEMA_PATH)
    # No companion resources are registered. Successful nested validation thus
    # proves Target, Access, Task, Message, and Artifact references are local.
    assert schema.get("$id") == _SCHEMA_ID.value
    assert schema.get("$schema") == _SCHEMA_DIALECT
    return SchemaValidatorAdapter(SchemaLoader({_SCHEMA_ID: schema}))


def _task_kind(identifier: str, composition: str) -> dict[str, JsonValue]:
    """Create one serialized TaskNode Kind value."""
    # Explicit field names keep task examples readable without weakening the
    # nested Kind contract exercised by each request fixture.
    return {"id": identifier, "composition": composition}


def _message_kind(
    identifier: str, category: str, composition: str
) -> dict[str, JsonValue]:
    """Create one serialized message element Kind value."""
    # Message Kind includes category and therefore remains separate from the
    # structurally similar but semantically independent task helper above.
    return {"id": identifier, "category": category, "composition": composition}


def _target() -> dict[str, JsonValue]:
    """Create the smallest complete serialized model target."""
    # Service, protocol, and model identity remain independent even in a compact
    # fixture; no endpoint or access data is inferred into this value.
    return {
        "serviceId": "service.local",
        "protocolId": "protocol.native",
        "model": {"name": "model"},
    }


def _task_root(children: list[JsonValue] | None = None) -> dict[str, JsonValue]:
    """Create a serialized TaskDocument root with ordered children."""
    # Allocate a fresh empty list for each call so fixtures cannot share mutable
    # child membership while testing independent request documents.
    return {
        "id": "task-root",
        "kind": _task_kind("task.root", "container"),
        "children": [] if children is None else children,
    }


def _task_request(
    *,
    task_type: str = "custom.task",
    children: list[JsonValue] | None = None,
    artifacts: list[JsonValue] | None = None,
) -> dict[str, JsonValue]:
    """Create one serialized open ModelTaskRequest."""
    # Descriptor, document, and concrete catalog are always explicit. Empty
    # artifacts means a resolved empty scope rather than missing catalog state.
    return {
        "descriptor": {"type": task_type},
        "document": {"version": "1.0", "root": _task_root(children)},
        "artifacts": {"artifacts": [] if artifacts is None else artifacts},
    }


def _conversation_input() -> dict[str, JsonValue]:
    """Create one valid conversation input node with ordered text content."""
    # The complete nested MessageDocument proves the outer schema does not replace
    # messages with a shortcut request field or an untyped placeholder mapping.
    return {
        "id": "input",
        "kind": _task_kind("task.input", "leaf"),
        "children": [],
        "messages": {
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
                                "text": "你好\nworld 👋",
                            }
                        ],
                    }
                ],
            },
        },
    }


def test_model_request_schema_is_registered_and_task_neutral() -> None:
    """Verify stable discovery and the exact outer request field boundary."""
    schema = _load_object(_SCHEMA_PATH)
    index = _load_object(_SCHEMA_INDEX_PATH)
    properties = schema.get("properties")
    resources = index.get("resources")
    if not isinstance(properties, dict) or not isinstance(resources, list):
        raise AssertionError("Schema properties and index resources must be objects.")

    # The outer envelope owns routing, task, optional access, and two preservation
    # channels only. Task configuration and runtime behavior remain nested or external.
    assert "model-request.json" in resources
    assert frozenset(properties) == frozenset(
        ("extensions", "metadata", "serviceAccess", "target", "task")
    )
    for unrelated_name in (
        "artifacts",
        "authorization",
        "components",
        "generationParameters",
        "interactionMode",
        "messages",
        "options",
        "protocolPayload",
        "temperature",
        "transport",
    ):
        assert unrelated_name not in properties


def test_model_request_schema_embeds_canonical_composed_contracts() -> None:
    """Verify independently loadable composed schemas cannot drift after embedding."""
    request_definitions = _definitions(_load_object(_SCHEMA_PATH))
    composed_resources = (
        (_TARGET_SCHEMA_PATH, "modelTarget"),
        (_ACCESS_SCHEMA_PATH, "serviceAccess"),
        (_TASK_SCHEMA_PATH, "taskDocument"),
        (_CATALOG_SCHEMA_PATH, "artifactCatalog"),
    )

    for path, definition_name in composed_resources:
        # Every embedded root is the canonical source minus only resource-local
        # identity and definition membership, which remain owned by this file.
        source = _load_object(path)
        assert request_definitions.get(definition_name) == _embedded_root(source)
        source_definitions = source.get("$defs")
        if source_definitions is None:
            continue
        if not isinstance(source_definitions, dict):
            raise AssertionError(f"Definitions must be an object in {path}.")
        for name, definition in source_definitions.items():
            assert request_definitions.get(name) == definition


def test_model_request_schema_defines_complete_task_protocol_boundaries() -> None:
    """Verify TaskDescriptor and ModelTaskRequest own their exact common fields."""
    definitions = _definitions(_load_object(_SCHEMA_PATH))
    descriptor = definitions.get("taskDescriptor")
    task = definitions.get("modelTaskRequest")
    if not isinstance(descriptor, dict) or not isinstance(task, dict):
        raise AssertionError("Task protocol definitions must be objects.")
    descriptor_properties = descriptor.get("properties")
    task_properties = task.get("properties")
    if not isinstance(descriptor_properties, dict) or not isinstance(
        task_properties, dict
    ):
        raise AssertionError("Task protocol properties must be objects.")

    # Descriptor keeps independent schema identities and open task type. The task
    # always carries one concrete ArtifactCatalog, including when it is empty.
    assert frozenset(descriptor_properties) == frozenset(
        (
            "extensions",
            "inputSchemaId",
            "metadata",
            "outputSchemaId",
            "type",
            "version",
        )
    )
    assert descriptor.get("required") == ["type"]
    assert frozenset(task_properties) == frozenset(
        ("artifacts", "descriptor", "document", "extensions", "metadata")
    )
    assert task.get("required") == ["artifacts", "descriptor", "document"]


def test_model_request_schema_accepts_minimal_and_complete_requests() -> None:
    """Verify unresolved access, standard conversation, and open tasks compose."""
    adapter = _adapter()
    minimal: JsonValue = {"target": _target(), "task": _task_request()}
    explicit_unresolved: JsonValue = {
        "target": _target(),
        "task": _task_request(),
        "serviceAccess": None,
    }
    conversation: JsonValue = {
        "target": {
            "serviceId": "service.vendor",
            "protocolId": "protocol.compatible",
            "model": {
                "name": "model-v2",
                "displayName": "Model V2",
                "family": "family.text",
                "version": "2026-10",
                "description": "Conversation model",
                "metadata": {"contextWindow": 128000},
                "extensions": {"vendor.model": True},
            },
            "deploymentId": "production-a",
            "extensions": {"vendor.routing": "east"},
        },
        "task": {
            **_task_request(
                task_type="conversation.generate",
                children=[
                    _conversation_input(),
                    {
                        "id": "configuration",
                        "kind": _task_kind("task.configuration", "leaf"),
                        "children": [],
                        "parameters": {
                            "temperature": 0.2,
                            "topP": 0.95,
                            "maxOutputTokens": 512,
                            "stop": ["END"],
                            "seed": 9,
                        },
                    },
                ],
            ),
            "metadata": {"task": "conversation"},
            "extensions": {"vendor.task": True},
        },
        "serviceAccess": {
            "endpoint": "https://models.example.test/v1",
            "headers": {"values": [{"name": "X-Feature", "value": "enabled"}]},
            "query": {"values": [{"name": "region", "value": "east"}]},
            "apiVersion": "2026-10-01",
            "projectId": "project-a",
            "tenantId": "tenant-a",
            "extensions": {"vendor.access": True},
        },
        "metadata": {"trace": "request-a"},
        "extensions": {"vendor.request": {"enabled": True}},
    }
    open_request: JsonValue = {
        "target": _target(),
        "task": {
            **_task_request(
                task_type="vendor.future_task",
                children=[
                    {
                        "id": "provider-node",
                        "kind": _task_kind("vendor.payload", "leaf"),
                        "children": [],
                        "providerPayload": {"mode": "future"},
                    }
                ],
                artifacts=[
                    {
                        "id": "artifact-1",
                        "kind": {"id": "artifact.file"},
                        "source": {
                            "kind": "vendor.object_store",
                            "objectKey": "objects/item",
                        },
                    }
                ],
            ),
            "descriptor": {
                "type": "vendor.future_task",
                "version": "2",
                "inputSchemaId": "schema.vendor.input",
                "outputSchemaId": "schema.vendor.output",
                "metadata": {"owner": "vendor"},
                "extensions": {"vendor.descriptor": True},
            },
        },
    }

    # These cases prove omitted and explicit-null access remain unresolved,
    # standard conversation data stays in TaskDocument, and future task payloads
    # plus Artifact sources survive one independently loaded request schema.
    for document in (minimal, explicit_unresolved, conversation, open_request):
        assert adapter.validate(_SCHEMA_ID, document) == ()


def test_model_request_schema_rejects_outer_and_composed_boundary_violations() -> None:
    """Verify required values, nested ownership, and sensitive fields fail."""
    adapter = _adapter()
    invalid_documents: tuple[
        tuple[JsonValue, tuple[SchemaValidationIssue, ...]], ...
    ] = (
        (
            {"task": _task_request()},
            (
                SchemaValidationIssue(
                    "/target", "required", "Required property is missing."
                ),
            ),
        ),
        (
            {"target": _target()},
            (
                SchemaValidationIssue(
                    "/task", "required", "Required property is missing."
                ),
            ),
        ),
        (
            {"target": _target(), "task": _task_request(), "messages": []},
            (
                SchemaValidationIssue(
                    "/messages",
                    "additionalProperties",
                    "Additional property is not allowed.",
                ),
            ),
        ),
        (
            {
                "target": {
                    "serviceId": "Invalid Service",
                    "protocolId": "protocol.native",
                    "model": {"name": "model"},
                },
                "task": _task_request(),
            },
            (
                SchemaValidationIssue(
                    "/target/serviceId", "pattern", "String does not match pattern."
                ),
            ),
        ),
        (
            {
                "target": _target(),
                "task": {
                    **_task_request(),
                    "descriptor": {"type": "custom.task", "version": "   "},
                },
            },
            (
                SchemaValidationIssue(
                    "/task/descriptor/version",
                    "pattern",
                    "String does not match pattern.",
                ),
            ),
        ),
        (
            {
                "target": _target(),
                "task": {
                    "descriptor": {"type": "custom.task"},
                    "document": {"version": "1.0", "root": _task_root()},
                },
            },
            (
                SchemaValidationIssue(
                    "/task/artifacts", "required", "Required property is missing."
                ),
            ),
        ),
        (
            {
                "target": _target(),
                "task": _task_request(),
                "serviceAccess": {"authorization": {"kind": "authorization.bearer"}},
            },
            (
                SchemaValidationIssue(
                    "/serviceAccess",
                    "oneOf",
                    "Value must match exactly one schema alternative.",
                ),
            ),
        ),
        (
            {
                "target": _target(),
                "task": _task_request(),
                "metadata": [],
            },
            (
                SchemaValidationIssue(
                    "/metadata", "type", "Value has an unexpected JSON type."
                ),
            ),
        ),
    )

    # Exact issues ensure outer shortcuts cannot bypass Task ownership, nested
    # schemas retain their paths, and runtime authorization never becomes JSON.
    for document, expected in invalid_documents:
        assert adapter.validate(_SCHEMA_ID, document) == expected


def test_model_request_schema_rejects_invalid_nested_task_and_artifact_values() -> None:
    """Verify TaskDocument and ArtifactCatalog remain active composed contracts."""
    adapter = _adapter()
    malformed_input: JsonValue = {
        "id": "input",
        "kind": _task_kind("task.input", "leaf"),
        "children": [],
    }
    invalid_task: JsonValue = {
        "target": _target(),
        "task": _task_request(
            task_type="conversation.generate", children=[malformed_input]
        ),
    }
    invalid_artifact: JsonValue = {
        "target": _target(),
        "task": _task_request(
            artifacts=[
                {
                    "id": "artifact-1",
                    "kind": {"id": "artifact.file"},
                    "source": {"kind": "artifact.inline"},
                }
            ]
        ),
    }

    # The task node union hides noisy branch details at the node path. Artifact
    # source alternatives likewise fail at their precise nested union boundary.
    assert adapter.validate(_SCHEMA_ID, invalid_task) == (
        SchemaValidationIssue(
            "/task/document/root/children/0",
            "oneOf",
            "Value must match exactly one schema alternative.",
        ),
    )
    assert adapter.validate(_SCHEMA_ID, invalid_artifact) == (
        SchemaValidationIssue(
            "/task/artifacts/artifacts/0/source",
            "oneOf",
            "Value must match exactly one schema alternative.",
        ),
    )


def test_model_request_schema_preserves_global_validation_evidence() -> None:
    """Verify whole-graph invariants remain available to domain validators."""
    duplicated_artifact: JsonValue = {
        "id": "duplicate",
        "kind": {"id": "artifact.file"},
        "source": {"kind": "vendor.object_store"},
    }
    duplicated_node: JsonValue = {
        "id": "duplicate",
        "kind": _task_kind("vendor.node", "leaf"),
        "children": [],
        "relations": [
            {
                "source": "duplicate",
                "target": "missing",
                "type": "task.references",
            }
        ],
    }
    document: JsonValue = {
        "target": _target(),
        "task": _task_request(
            children=[duplicated_node, dict(duplicated_node)],
            artifacts=[duplicated_artifact, dict(duplicated_artifact)],
        ),
    }

    # Basic JSON Schema cannot express uniqueness by a member field or resolve
    # relation endpoints across a recursive tree. Keeping evidence intact lets
    # TaskDocument and ArtifactCatalog validators return stable domain failures.
    assert _adapter().validate(_SCHEMA_ID, document) == ()
