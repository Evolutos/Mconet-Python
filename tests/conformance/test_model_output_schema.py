"""Conformance checks for the standalone ModelOutput schema."""

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
_SCHEMA_PATH = _SCHEMA_ROOT / "model-output.json"
_SCHEMA_INDEX_PATH = _SCHEMA_ROOT / "index.json"
_TARGET_SCHEMA_PATH = _SCHEMA_ROOT / "model-target.json"
_DESCRIPTOR_SCHEMA_PATH = _SCHEMA_ROOT / "model-descriptor.json"
_TASK_SCHEMA_PATH = _SCHEMA_ROOT / "task-document.json"
_CATALOG_SCHEMA_PATH = _SCHEMA_ROOT / "artifact-catalog.json"
_SCHEMA_ID = OpenIdentifier("schema.model_output")
_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"


def _load_object(path: Path) -> dict[str, JsonValue]:
    """Load one committed UTF-8 JSON object document."""
    document: JsonValue = json.loads(path.read_text(encoding="utf-8"))
    # Every schema and collection index used here requires named root fields, so
    # reject unrelated scalar or array documents before inspecting membership.
    if not isinstance(document, dict):
        raise AssertionError(f"Expected a JSON object in {path}.")
    return document


def _embedded_root(schema: dict[str, JsonValue]) -> dict[str, JsonValue]:
    """Return a schema root without resource identity or local definitions."""
    # Only top-level membership changes during embedding; nested contract data
    # stays shared read-only within this test and is compared without mutation.
    embedded = dict(schema)
    embedded.pop("$defs", None)
    embedded.pop("$id", None)
    embedded.pop("$schema", None)
    return embedded


def _definitions(schema: dict[str, JsonValue]) -> dict[str, JsonValue]:
    """Return one schema's object-valued local definition map."""
    definitions = schema.get("$defs")
    # Definition parity cannot be established from a missing or non-object map;
    # fail as malformed committed data rather than treating it as empty.
    if not isinstance(definitions, dict):
        raise AssertionError("Schema definitions must be an object.")
    return definitions


def _adapter() -> SchemaValidatorAdapter:
    """Load only the output schema through the public validation toolchain."""
    schema = _load_object(_SCHEMA_PATH)
    # No companion resource registration is allowed here. Successful validation
    # proves every Model, Task, Message, Artifact, and output reference is local.
    assert schema.get("$id") == _SCHEMA_ID.value
    assert schema.get("$schema") == _SCHEMA_DIALECT
    return SchemaValidatorAdapter(SchemaLoader({_SCHEMA_ID: schema}))


def _task_kind(identifier: str, composition: str) -> dict[str, JsonValue]:
    """Create one serialized TaskNode Kind value."""
    # Explicit field names make result-tree examples readable while exercising
    # the same nested Kind contract used by independently serialized documents.
    return {"id": identifier, "composition": composition}


def _message_kind(
    identifier: str, category: str, composition: str
) -> dict[str, JsonValue]:
    """Create one serialized message element Kind value."""
    # Message Kind carries category in addition to the task Kind dimensions and
    # therefore remains a separate domain-specific fixture helper.
    return {"id": identifier, "category": category, "composition": composition}


def _target() -> dict[str, JsonValue]:
    """Create the smallest complete serialized request-retained target."""
    # Target preserves requested routing only; actual service model information
    # remains independently optional in resolvedModel.
    return {
        "serviceId": "service.local",
        "protocolId": "protocol.native",
        "model": {"name": "requested-model"},
    }


def _task_root(children: list[JsonValue] | None = None) -> dict[str, JsonValue]:
    """Create a generic serialized result TaskDocument root."""
    # Allocate fresh empty membership for each result so fixtures cannot affect
    # one another through a shared mutable child list.
    return {
        "id": "task-root",
        "kind": _task_kind("task.root", "container"),
        "children": [] if children is None else children,
    }


def _open_result(
    *,
    task_type: str = "vendor.result",
    children: list[JsonValue] | None = None,
    artifacts: list[JsonValue] | None = None,
) -> dict[str, JsonValue]:
    """Create one complete serialized open ModelTaskResult."""
    # Descriptor, document, and result-local catalog are all explicit; an empty
    # Artifact list represents a concrete local scope rather than missing data.
    return {
        "descriptor": {"type": task_type},
        "document": {"version": "1.0", "root": _task_root(children)},
        "artifacts": {"artifacts": [] if artifacts is None else artifacts},
    }


def _output_messages(
    *, purpose: str = "output", text: str = "answer"
) -> dict[str, JsonValue]:
    """Create one serialized conversation output MessageDocument."""
    # A concrete assistant entry proves output messages retain their own tree,
    # role, content order, Unicode text, and purpose below the task result node.
    return {
        "version": "1.0",
        "purpose": purpose,
        "root": {
            "id": "messages",
            "kind": _message_kind("message.root", "group", "container"),
            "subElements": [
                {
                    "id": "entry-1",
                    "kind": _message_kind("message.entry", "entry", "leaf"),
                    "subElements": [],
                    "role": {"id": "message.assistant"},
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


def _conversation_result(
    *, messages: dict[str, JsonValue] | None = None
) -> dict[str, JsonValue]:
    """Create the canonical serialized conversation task result tree."""
    # The public result shape remains ModelTaskResult. Message data appears once
    # inside the fixed task.result leaf rather than as a result or output shortcut.
    return {
        "descriptor": {"type": "conversation.generate"},
        "document": {
            "version": "1.0",
            "root": {
                "id": "root",
                "kind": _task_kind("task.root", "container"),
                "children": [
                    {
                        "id": "result",
                        "kind": _task_kind("task.result", "leaf"),
                        "children": [],
                        "messages": _output_messages()
                        if messages is None
                        else messages,
                    }
                ],
            },
        },
        "artifacts": {"artifacts": []},
    }


def test_model_output_schema_is_registered_and_task_neutral() -> None:
    """Verify stable discovery and the exact assembled output field boundary."""
    schema = _load_object(_SCHEMA_PATH)
    index = _load_object(_SCHEMA_INDEX_PATH)
    properties = schema.get("properties")
    resources = index.get("resources")
    if not isinstance(properties, dict) or not isinstance(resources, list):
        raise AssertionError("Schema properties and index resources must be objects.")

    # The exact surface mirrors Runtime assembly ownership. Task projections,
    # request access, transport state, and mutable runtime controls remain absent.
    assert "model-output.json" in resources
    assert frozenset(properties) == frozenset(
        (
            "diagnostics",
            "extensions",
            "id",
            "protocolState",
            "resolvedModel",
            "result",
            "status",
            "stopReason",
            "target",
            "usage",
        )
    )
    for unrelated_name in (
        "authorization",
        "error",
        "messages",
        "request",
        "serviceAccess",
        "text",
        "transport",
    ):
        assert unrelated_name not in properties


def test_model_output_schema_embeds_canonical_composed_contracts() -> None:
    """Verify independently published input contracts remain structurally exact."""
    output_definitions = _definitions(_load_object(_SCHEMA_PATH))
    composed_resources = (
        (_TARGET_SCHEMA_PATH, "modelTarget"),
        (_DESCRIPTOR_SCHEMA_PATH, "modelDescriptor"),
        (_TASK_SCHEMA_PATH, "taskDocument"),
        (_CATALOG_SCHEMA_PATH, "artifactCatalog"),
    )

    for path, definition_name in composed_resources:
        # Embedded roots remove only resource-local identity and definitions; all
        # validation fields remain byte-shape equivalent to their canonical source.
        source = _load_object(path)
        assert output_definitions.get(definition_name) == _embedded_root(source)
        source_definitions = source.get("$defs")
        if source_definitions is None:
            continue
        if not isinstance(source_definitions, dict):
            raise AssertionError(f"Definitions must be an object in {path}.")
        for name, definition in source_definitions.items():
            assert output_definitions.get(name) == definition


def test_model_output_schema_defines_exact_output_value_contracts() -> None:
    """Verify status, usage, state, diagnostics, and result ownership are explicit."""
    definitions = _definitions(_load_object(_SCHEMA_PATH))
    usage = definitions.get("tokenUsage")
    state = definitions.get("protocolState")
    diagnostic = definitions.get("diagnostic")
    result = definitions.get("modelTaskResult")
    if any(not isinstance(value, dict) for value in (usage, state, diagnostic, result)):
        raise AssertionError("Output value definitions must be objects.")

    # Token counts remain independently optional and bounded. Protocol state
    # requires all identity dimensions plus a present value, including JSON null.
    assert isinstance(usage, dict)
    usage_properties = usage.get("properties")
    assert isinstance(usage_properties, dict)
    assert frozenset(usage_properties) == frozenset(
        ("extensions", "inputTokens", "outputTokens", "totalTokens")
    )
    for name in ("inputTokens", "outputTokens", "totalTokens"):
        count = usage_properties.get(name)
        assert isinstance(count, dict)
        assert count.get("minimum") == 0
        assert count.get("maximum") == 9_007_199_254_740_991

    assert isinstance(state, dict)
    assert state.get("required") == [
        "protocolId",
        "serviceId",
        "stateType",
        "stateValue",
    ]
    assert isinstance(diagnostic, dict)
    assert diagnostic.get("required") == ["code", "message", "phase", "severity"]
    assert isinstance(result, dict)
    assert result.get("oneOf") == [
        {"$ref": "#/$defs/conversationTaskResult"},
        {"$ref": "#/$defs/openModelTaskResult"},
    ]


def test_model_output_schema_accepts_minimal_and_complete_outputs() -> None:
    """Verify absent facts, complete conversation data, and open results compose."""
    adapter = _adapter()
    minimal: JsonValue = {
        "target": _target(),
        "status": "completed",
        "result": _open_result(),
    }
    explicit_absence: JsonValue = {
        "id": None,
        "target": _target(),
        "resolvedModel": None,
        "status": "unknown",
        "result": _open_result(),
        "stopReason": None,
        "usage": None,
        "diagnostics": [],
        "protocolState": [],
    }
    conversation: JsonValue = {
        "id": "output-1",
        "target": {
            "serviceId": "service.vendor",
            "protocolId": "protocol.compatible",
            "model": {"name": "requested-model"},
            "deploymentId": "production-a",
            "extensions": {"vendor.routing": "east"},
        },
        "resolvedModel": {
            "name": "actual-model",
            "displayName": "Actual Model",
            "family": "family.text",
            "version": "2026-10",
            "description": "Resolved service model",
            "metadata": {"region": "east"},
            "extensions": {"vendor.alias": "stable"},
        },
        "status": "requires_action",
        "result": {
            **_conversation_result(),
            "metadata": {"task": "conversation"},
            "extensions": {"vendor.result": True},
        },
        "stopReason": "tool_calls",
        "usage": {
            "inputTokens": 11,
            "outputTokens": 7,
            "totalTokens": 25,
            "extensions": {"cachedInputTokens": 3},
        },
        "diagnostics": [
            {
                "code": "response_warning",
                "severity": "warning",
                "phase": "response",
                "message": "Provider returned a warning.",
                "path": "/result",
                "serviceId": "service.vendor",
                "details": {"retryable": False},
            },
            {
                "code": "runtime_note",
                "severity": "info",
                "phase": "validation",
                "message": "Output validated.",
                "path": None,
                "serviceId": None,
                "details": None,
            },
        ],
        "protocolState": [
            {
                "serviceId": "service.vendor",
                "protocolId": "protocol.compatible",
                "stateType": "state.cursor",
                "stateValue": {"cursor": "next-2"},
            },
            {
                "serviceId": "service.vendor",
                "protocolId": "protocol.compatible",
                "stateType": "state.empty",
                "stateValue": None,
            },
        ],
        "extensions": {"vendor.responseId": "response-9"},
    }
    open_output: JsonValue = {
        "target": _target(),
        "status": "vendor.awaiting_review",
        "result": {
            **_open_result(
                task_type="vendor.future_result",
                children=[
                    {
                        "id": "provider-result",
                        "kind": _task_kind("vendor.result", "leaf"),
                        "children": [],
                        "providerPayload": {"score": 0.98},
                    }
                ],
                artifacts=[
                    {
                        "id": "artifact-1",
                        "kind": {"id": "artifact.file"},
                        "source": {
                            "kind": "vendor.object_store",
                            "objectKey": "objects/result",
                        },
                    }
                ],
            ),
            "descriptor": {
                "type": "vendor.future_result",
                "version": "2",
                "outputSchemaId": "schema.vendor.output",
                "metadata": {"owner": "vendor"},
                "extensions": {"vendor.descriptor": True},
            },
        },
    }

    # Minimal output permits omitted default/absent facts; complete and open cases
    # exercise every owner without deriving target model, usage, status, or data.
    for document in (minimal, explicit_absence, conversation, open_output):
        assert adapter.validate(_SCHEMA_ID, document) == ()


def test_model_output_schema_rejects_outer_and_value_boundary_violations() -> None:
    """Verify required fields, ownership, and nested value semantics fail."""
    adapter = _adapter()
    invalid_documents: tuple[
        tuple[JsonValue, tuple[SchemaValidationIssue, ...]], ...
    ] = (
        (
            {"status": "completed", "result": _open_result()},
            (
                SchemaValidationIssue(
                    "/target", "required", "Required property is missing."
                ),
            ),
        ),
        (
            {"target": _target(), "result": _open_result()},
            (
                SchemaValidationIssue(
                    "/status", "required", "Required property is missing."
                ),
            ),
        ),
        (
            {"target": _target(), "status": "completed"},
            (
                SchemaValidationIssue(
                    "/result", "required", "Required property is missing."
                ),
            ),
        ),
        (
            {
                "target": _target(),
                "status": "completed",
                "result": _open_result(),
                "text": "shortcut",
            },
            (
                SchemaValidationIssue(
                    "/text",
                    "additionalProperties",
                    "Additional property is not allowed.",
                ),
            ),
        ),
        (
            {
                "target": _target(),
                "status": "Invalid Status",
                "result": _open_result(),
            },
            (
                SchemaValidationIssue(
                    "/status", "pattern", "String does not match pattern."
                ),
            ),
        ),
        (
            {
                "target": _target(),
                "resolvedModel": {},
                "status": "completed",
                "result": _open_result(),
            },
            (
                SchemaValidationIssue(
                    "/resolvedModel",
                    "oneOf",
                    "Value must match exactly one schema alternative.",
                ),
            ),
        ),
        (
            {
                "target": _target(),
                "status": "completed",
                "result": _open_result(),
                "usage": {"inputTokens": -1},
            },
            (
                SchemaValidationIssue(
                    "/usage",
                    "oneOf",
                    "Value must match exactly one schema alternative.",
                ),
            ),
        ),
        (
            {
                "target": _target(),
                "status": "completed",
                "result": _open_result(),
                "diagnostics": [
                    {
                        "code": "invalid",
                        "severity": "fatal",
                        "phase": "validation",
                        "message": "Invalid severity.",
                    }
                ],
            },
            (
                SchemaValidationIssue(
                    "/diagnostics/0/severity",
                    "enum",
                    "Value is not an allowed enum member.",
                ),
            ),
        ),
        (
            {
                "target": _target(),
                "status": "completed",
                "result": _open_result(),
                "protocolState": [
                    {
                        "serviceId": "service.vendor",
                        "protocolId": "protocol.native",
                        "stateType": "state.cursor",
                    }
                ],
            },
            (
                SchemaValidationIssue(
                    "/protocolState/0/stateValue",
                    "required",
                    "Required property is missing.",
                ),
            ),
        ),
    )

    # Exact issues freeze deterministic paths and prove result projections or
    # malformed parsed facts cannot bypass their independently owned contracts.
    for document, expected in invalid_documents:
        assert adapter.validate(_SCHEMA_ID, document) == expected


def test_model_output_schema_rejects_malformed_conversation_results() -> None:
    """Verify the standard task identity cannot fall through the open result branch."""
    adapter = _adapter()
    empty_document = _open_result(task_type="conversation.generate")
    wrong_purpose = _conversation_result(messages=_output_messages(purpose="input"))
    missing_message_node = _conversation_result()
    document = missing_message_node.get("document")
    if not isinstance(document, dict):
        raise AssertionError("Conversation result document must be an object.")
    root = document.get("root")
    if not isinstance(root, dict):
        raise AssertionError("Conversation result root must be an object.")
    root["children"] = []
    extra_node = _conversation_result()
    extra_document = extra_node.get("document")
    if not isinstance(extra_document, dict):
        raise AssertionError("Conversation result document must be an object.")
    extra_root = extra_document.get("root")
    if not isinstance(extra_root, dict):
        raise AssertionError("Conversation result root must be an object.")
    children = extra_root.get("children")
    if not isinstance(children, list) or not children:
        raise AssertionError("Conversation result children must be non-empty.")
    first_child = children[0]
    if not isinstance(first_child, dict):
        raise AssertionError("Conversation result child must be an object.")
    # Duplicate the complete result-node membership to exercise the upper bound
    # without changing the validity of either individual child object.
    children.append(dict(first_child))
    invalid_results: tuple[JsonValue, ...] = (
        empty_document,
        wrong_purpose,
        missing_message_node,
        extra_node,
    )
    expected = (
        SchemaValidationIssue(
            "/result",
            "oneOf",
            "Value must match exactly one schema alternative.",
        ),
    )

    # The conversation descriptor is excluded from the open branch. Therefore an
    # empty tree, input-purpose messages, and child cardinality errors all fail the
    # standard result as a whole instead of becoming provider-defined results.
    for result in invalid_results:
        output: JsonValue = {
            "target": _target(),
            "status": "completed",
            "result": result,
        }
        assert adapter.validate(_SCHEMA_ID, output) == expected


def test_model_output_schema_preserves_global_validation_evidence() -> None:
    """Verify graph and catalog invariants remain available to domain validators."""
    duplicated_node: JsonValue = {
        "id": "duplicate",
        "kind": _task_kind("vendor.result", "leaf"),
        "children": [],
        "relations": [
            {
                "source": "duplicate",
                "target": "missing",
                "type": "task.references",
            }
        ],
    }
    duplicated_artifact: JsonValue = {
        "id": "duplicate",
        "kind": {"id": "artifact.file"},
        "source": {"kind": "vendor.object_store"},
    }
    output: JsonValue = {
        "target": _target(),
        "status": "completed",
        "result": _open_result(
            children=[duplicated_node, dict(duplicated_node)],
            artifacts=[duplicated_artifact, dict(duplicated_artifact)],
        ),
    }

    # JSON Schema cannot express uniqueness by a nested ID or resolve relation
    # endpoints across a recursive tree. Preserving both entries lets existing
    # TaskDocument and ArtifactCatalog validators return stable domain failures.
    assert _adapter().validate(_SCHEMA_ID, output) == ()
