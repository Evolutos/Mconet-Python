"""Conformance checks for the language-neutral Conversation Result fixture."""

from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Literal, Protocol, cast, runtime_checkable

from mconet.core.domain import (
    ArtifactCatalog,
    ConversationTaskResult,
    Diagnostic,
    Extensions,
    InteractionPhase,
    JsonValue,
    MessageDocument,
    MessageElement,
    MessageElementKind,
    MessageEntry,
    MessageGroup,
    MessageRole,
    ModelDescriptor,
    ModelOutput,
    ModelRequest,
    ModelRequestBuilder,
    ModelTarget,
    ModelTaskRequest,
    NamedModel,
    OpenIdentifier,
    OutputStatus,
    ParsedTaskResponse,
    ProtocolState,
    TaskDescriptor,
    TaskDocument,
    TaskGroupNode,
    TaskNodeKind,
    TextMessageContent,
    TokenUsage,
)
from mconet.core.runtime.model_output_assembler import ModelOutputAssembler
from mconet.testing import (
    SchemaLoader,
    SchemaValidatorAdapter,
    json_fixtures_equal,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_FIXTURE_ROOT = _PROJECT_ROOT / "spec" / "fixtures" / "r1-text-unary"
_FIXTURE_PATH = _FIXTURE_ROOT / "conversation-result.json"
_INDEX_PATH = _FIXTURE_ROOT / "index.json"
_SCHEMA_PATH = _PROJECT_ROOT / "spec" / "schemas" / "model-output.json"
_SCHEMA_ID = OpenIdentifier("schema.model_output")
_CASE_NAME = "ordered-assistant-text-and-completion-facts"
_EMPTY_EXTENSIONS: Extensions = MappingProxyType({})


def _empty_extensions() -> Extensions:
    """Return immutable empty data for omitted fixture mapping channels."""
    # The shared mapping has no nested state and rejects membership changes, so
    # omitted fields can reuse it without coupling reconstructed result values.
    return _EMPTY_EXTENSIONS


@dataclass(frozen=True, slots=True)
class _FixtureMessageKind:
    """Represent one open message group Kind decoded from fixture JSON."""

    id: OpenIdentifier
    """Portable standard or provider-defined Kind identity."""

    category: str
    """Producer-defined message element category."""

    composition: Literal["leaf", "container"]
    """Tree composition retained independently from Kind identity."""


@dataclass(frozen=True, slots=True)
class _FixtureMessageRole:
    """Represent one standard or provider-defined role decoded from JSON."""

    id: OpenIdentifier
    """Portable role identity retained without a closed known-role table."""

    semantic: str | None = None
    """Optional producer guidance for role semantics."""

    raw_value: str | None = None
    """Optional exact external role spelling."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Unknown role data preserved without interpretation."""


@runtime_checkable
class _FixtureMessageCarrier(Protocol):
    """Describe the private result node's observable message-bearing surface."""

    @property
    def messages(self) -> MessageDocument:
        """Return the independent output MessageDocument carried by the node."""
        # Structural access keeps the production node implementation private while
        # giving the conformance serializer a checked, read-only message boundary.
        ...


@dataclass(frozen=True, slots=True)
class _FixtureTarget:
    """Provide a complete structural ModelTarget reconstructed from JSON."""

    service_id: OpenIdentifier
    """Selected model service identity."""

    protocol_id: OpenIdentifier
    """Selected protocol identity."""

    model: ModelDescriptor
    """Requested model descriptor."""

    deployment_id: str | None
    """Optional service deployment identity."""

    extensions: Extensions
    """Unknown target data retained from the fixture."""


@dataclass(frozen=True, slots=True)
class _FixtureTaskKind:
    """Provide the container Kind for the assembler's request-only task."""

    id: OpenIdentifier
    """Open task node Kind identity."""

    composition: Literal["leaf", "container"]
    """Tree composition used by common TaskDocument validation."""


@dataclass(frozen=True, slots=True)
class _FixtureTaskDescriptor:
    """Provide an open request task descriptor used only for output assembly."""

    type: OpenIdentifier
    """Open task identity deliberately independent from result task identity."""

    version: str | None
    """Optional task contract version."""

    input_schema_id: str | None
    """Optional request input schema identity."""

    output_schema_id: str | None
    """Optional request output schema identity."""

    metadata: Extensions
    """Portable descriptor metadata."""

    extensions: Extensions
    """Unknown descriptor fields."""


@dataclass(frozen=True, slots=True)
class _FixtureRequestTask:
    """Provide a valid open request task for ModelOutputAssembler input."""

    descriptor: TaskDescriptor
    """Task identity retained only by the originating request."""

    document: TaskDocument
    """Minimal valid request task tree."""

    artifacts: ArtifactCatalog
    """Concrete request-local Artifact scope."""

    metadata: Extensions
    """Portable request task metadata."""

    extensions: Extensions
    """Unknown request task fields."""


def _load_object(path: Path) -> dict[str, JsonValue]:
    """Load one committed UTF-8 JSON document and require an object root."""
    document: JsonValue = json.loads(path.read_text(encoding="utf-8"))
    # Fixture resources use named envelopes. Rejecting scalar or array roots
    # prevents host languages from interpreting the same resource differently.
    if not isinstance(document, dict):
        raise AssertionError(f"Expected a JSON object in {path}.")
    return document


def _require_object(value: JsonValue | None, field_name: str) -> dict[str, JsonValue]:
    """Return one required object-valued fixture field."""
    # Reject absent, null, scalar, and array values before domain construction so
    # every malformed field receives the same location-specific diagnostic.
    if not isinstance(value, dict):
        raise AssertionError(f"{field_name} must be a JSON object.")
    return value


def _require_array(value: JsonValue | None, field_name: str) -> list[JsonValue]:
    """Return one required array-valued fixture field in source order."""
    # Arrays carry conformance order for messages, content, states, diagnostics,
    # and cases; never convert their membership to a set or keyed collection.
    if not isinstance(value, list):
        raise AssertionError(f"{field_name} must be a JSON array.")
    return value


def _require_string(value: JsonValue | None, field_name: str) -> str:
    """Return one required JSON string without coercion or normalization."""
    # Numeric, Boolean, null, and composite values cannot be stringified because
    # doing so would create platform-specific identifiers or response text.
    if not isinstance(value, str):
        raise AssertionError(f"{field_name} must be a JSON string.")
    return value


def _optional_string(value: JsonValue | None, field_name: str) -> str | None:
    """Return an optional nullable string while rejecting other JSON kinds."""
    # Missing and explicit null share the domain None representation. A present
    # string stays exact and is never trimmed, case-folded, or Unicode-normalized.
    if value is not None and not isinstance(value, str):
        raise AssertionError(f"{field_name} must be a JSON string or null.")
    return value


def _optional_integer(value: JsonValue | None, field_name: str) -> int | None:
    """Return one optional exact JSON integer while excluding booleans."""
    if value is None:
        # Missing token counts remain absent rather than being synthesized as zero
        # or derived from either of the independently reported sibling counts.
        return None
    if type(value) is not int:
        raise AssertionError(f"{field_name} must be a JSON integer or null.")
    return value


def _mapping_or_empty(document: dict[str, JsonValue], field_name: str) -> Extensions:
    """Decode an omitted JSON object channel as immutable empty data."""
    # Present mappings remain uninterpreted until composed production Validators
    # enforce recursive portable JSON and finite-number semantics.
    if field_name not in document:
        return _EMPTY_EXTENSIONS
    return _require_object(document[field_name], field_name)


def _decode_model(document: dict[str, JsonValue], field_name: str) -> ModelDescriptor:
    """Decode one complete open model descriptor without inferred fields."""
    family_value = document.get("family")
    family = (
        None
        if family_value is None
        else OpenIdentifier(_require_string(family_value, f"{field_name}.family"))
    )
    # NamedModel preserves every optional fact independently; a target model never
    # fills fields omitted from the service-reported resolved model or vice versa.
    return NamedModel(
        name=_require_string(document.get("name"), f"{field_name}.name"),
        display_name=_optional_string(
            document.get("displayName"), f"{field_name}.displayName"
        ),
        family=family,
        version=_optional_string(document.get("version"), f"{field_name}.version"),
        description=_optional_string(
            document.get("description"), f"{field_name}.description"
        ),
        metadata=_mapping_or_empty(document, "metadata"),
        extensions=_mapping_or_empty(document, "extensions"),
    )


def _decode_target(value: JsonValue | None) -> ModelTarget:
    """Decode the exact request-owned target retained by ModelOutput."""
    document = _require_object(value, "output.target")
    # Endpoint and authorization remain absent because ModelTarget owns only model
    # selection and routing identity, even when reconstructed for Runtime assembly.
    return _FixtureTarget(
        service_id=OpenIdentifier(
            _require_string(document.get("serviceId"), "target.serviceId")
        ),
        protocol_id=OpenIdentifier(
            _require_string(document.get("protocolId"), "target.protocolId")
        ),
        model=_decode_model(
            _require_object(document.get("model"), "target.model"), "target.model"
        ),
        deployment_id=_optional_string(
            document.get("deploymentId"), "target.deploymentId"
        ),
        extensions=_mapping_or_empty(document, "extensions"),
    )


def _decode_message_kind(value: JsonValue | None) -> MessageElementKind:
    """Decode one complete container MessageElement Kind."""
    document = _require_object(value, "message.kind")
    composition = _require_string(
        document.get("composition"), "message.kind.composition"
    )
    # Schema already narrows composition, while this explicit check keeps direct
    # helper calls inside the Literal contract enforced by static analysis.
    if composition not in ("leaf", "container"):
        raise AssertionError("message.kind.composition must be leaf or container.")
    return _FixtureMessageKind(
        OpenIdentifier(_require_string(document.get("id"), "message.kind.id")),
        _require_string(document.get("category"), "message.kind.category"),
        composition,
    )


def _decode_role(value: JsonValue | None) -> MessageRole:
    """Decode one open message role and all optional preservation data."""
    document = _require_object(value, "message.role")
    # A structural role avoids closed enumeration mapping, preserving future role
    # identity and hints through the same conversation result representation.
    return _FixtureMessageRole(
        id=OpenIdentifier(_require_string(document.get("id"), "message.role.id")),
        semantic=_optional_string(document.get("semantic"), "message.role.semantic"),
        raw_value=_optional_string(document.get("rawValue"), "message.role.rawValue"),
        extensions=_mapping_or_empty(document, "extensions"),
    )


def _decode_content(value: JsonValue) -> TextMessageContent:
    """Decode one text content segment without Unicode normalization."""
    document = _require_object(value, "message.content")
    kind = _require_object(document.get("kind"), "message.content.kind")
    # This result fixture belongs to the text-only profile; accepting another Kind
    # would weaken the fixture even if an open MessageContent implementation exists.
    if _require_string(kind.get("id"), "message.content.kind.id") != "content.text":
        raise AssertionError("Conversation Result content must use content.text.")
    return TextMessageContent(
        id=_require_string(document.get("id"), "message.content.id"),
        text=_require_string(document.get("text"), "message.content.text"),
        metadata=_mapping_or_empty(document, "metadata"),
        extensions=_mapping_or_empty(document, "extensions"),
    )


def _decode_message_element(value: JsonValue) -> MessageElement:
    """Recursively decode one result message group or concrete entry."""
    document = _require_object(value, "message.element")
    children = _require_array(document.get("subElements"), "message.subElements")
    element_id = _require_string(document.get("id"), "message.id")
    kind_document = _require_object(document.get("kind"), "message.kind")
    kind_id = _require_string(kind_document.get("id"), "message.kind.id")

    if kind_id == "message.entry":
        # Concrete entries are always leaves. Validate the serialized fixed Kind
        # fields instead of silently discarding a contradictory fixture value.
        if children:
            raise AssertionError("MessageEntry subElements must be empty.")
        if (
            kind_document.get("category") != "entry"
            or kind_document.get("composition") != "leaf"
        ):
            raise AssertionError("MessageEntry Kind fields must be canonical.")
        content_values = _require_array(document.get("content"), "message.content")
        return MessageEntry(
            id=element_id,
            role=_decode_role(document.get("role")),
            content=tuple(_decode_content(item) for item in content_values),
            metadata=_mapping_or_empty(document, "metadata"),
            extensions=_mapping_or_empty(document, "extensions"),
        )

    # Non-entry elements in this fixture are ordered containers. Payload values,
    # relations, and generic attributes are intentionally absent from this case.
    kind = _decode_message_kind(kind_document)
    if kind.composition != "container":
        raise AssertionError("Result message groups must be containers.")
    return MessageGroup(
        id=element_id,
        kind=kind,
        sub_elements=tuple(_decode_message_element(item) for item in children),
        metadata=_mapping_or_empty(document, "metadata"),
        extensions=_mapping_or_empty(document, "extensions"),
    )


def _decode_messages(value: JsonValue | None) -> MessageDocument:
    """Decode the independent output MessageDocument carried by the result."""
    document = _require_object(value, "result.messages")
    purpose = _require_string(document.get("purpose"), "messages.purpose")
    # The concrete constructor accepts all document purposes, but this fixture is
    # result-specific and must never repurpose an input or context document.
    if purpose != "output":
        raise AssertionError("Conversation Result messages purpose must be output.")
    root = _decode_message_element(document.get("root"))
    if not isinstance(root, MessageGroup):
        raise AssertionError("Conversation Result messages root must be a group.")
    return MessageDocument(
        version=_require_string(document.get("version"), "messages.version"),
        purpose="output",
        root=root,
        metadata=_mapping_or_empty(document, "metadata"),
        extensions=_mapping_or_empty(document, "extensions"),
    )


def _decode_result(value: JsonValue | None) -> ConversationTaskResult:
    """Decode the canonical conversation result and verify generated tree shape."""
    document = _require_object(value, "output.result")
    descriptor = _require_object(document.get("descriptor"), "result.descriptor")
    if descriptor != {"type": "conversation.generate"}:
        raise AssertionError("Conversation Result descriptor must be canonical.")
    catalog = _require_object(document.get("artifacts"), "result.artifacts")
    if _require_array(catalog.get("artifacts"), "result.artifacts.artifacts"):
        raise AssertionError("Conversation Result Fixture artifacts must be empty.")

    task_document = _require_object(document.get("document"), "result.document")
    root = _require_object(task_document.get("root"), "result.document.root")
    children = _require_array(root.get("children"), "result.document.root.children")
    if len(children) != 1:
        raise AssertionError("Conversation Result document must contain one child.")
    node = _require_object(children[0], "result.document.resultNode")
    result = ConversationTaskResult(
        messages=_decode_messages(node.get("messages")),
        artifacts=ArtifactCatalog(),
        metadata=_mapping_or_empty(document, "metadata"),
        extensions=_mapping_or_empty(document, "extensions"),
    )
    # Construction owns the fixed TaskDocument. Comparing its later serialization
    # to the fixture proves the fixture did not inject or bypass that invariant.
    return result


def _decode_usage(value: JsonValue | None) -> TokenUsage | None:
    """Decode optional provider token accounting without deriving any count."""
    if value is None:
        # Whole-object absence remains distinct from a present usage object whose
        # individual counts happen to be null or zero.
        return None
    document = _require_object(value, "output.usage")
    return TokenUsage(
        input_tokens=_optional_integer(document.get("inputTokens"), "usage.input"),
        output_tokens=_optional_integer(document.get("outputTokens"), "usage.output"),
        total_tokens=_optional_integer(document.get("totalTokens"), "usage.total"),
        extensions=_mapping_or_empty(document, "extensions"),
    )


def _decode_protocol_state(value: JsonValue) -> ProtocolState:
    """Decode one ordered opaque protocol state fact."""
    document = _require_object(value, "output.protocolState[]")
    if "stateValue" not in document:
        raise AssertionError("Protocol state must contain stateValue.")
    # State value is intentionally passed through as JsonValue, including a future
    # explicit JSON null, because Core validates but never interprets it.
    return ProtocolState(
        service_id=OpenIdentifier(
            _require_string(document.get("serviceId"), "state.serviceId")
        ),
        protocol_id=OpenIdentifier(
            _require_string(document.get("protocolId"), "state.protocolId")
        ),
        state_type=OpenIdentifier(
            _require_string(document.get("stateType"), "state.stateType")
        ),
        state_value=document["stateValue"],
    )


def _decode_diagnostic(value: JsonValue) -> Diagnostic:
    """Decode one Runtime-owned diagnostic without merging protocol facts."""
    document = _require_object(value, "output.diagnostics[]")
    severity = _require_string(document.get("severity"), "diagnostic.severity")
    if severity not in ("info", "warning", "error"):
        raise AssertionError("Diagnostic severity must be info, warning, or error.")
    service_value = document.get("serviceId")
    service_id = (
        None
        if service_value is None
        else OpenIdentifier(_require_string(service_value, "diagnostic.serviceId"))
    )
    # details is optional at the Diagnostic boundary. A present JSON null and an
    # omitted field both map to None, matching the published domain representation.
    return Diagnostic(
        code=_require_string(document.get("code"), "diagnostic.code"),
        severity=severity,
        phase=InteractionPhase(
            OpenIdentifier(_require_string(document.get("phase"), "diagnostic.phase"))
        ),
        message=_require_string(document.get("message"), "diagnostic.message"),
        path=_optional_string(document.get("path"), "diagnostic.path"),
        service_id=service_id,
        details=document.get("details"),
    )


def _request_for_target(target: ModelTarget) -> ModelRequest:
    """Build one valid open request whose exact target Runtime must retain."""
    kind: TaskNodeKind = _FixtureTaskKind(OpenIdentifier("task.root"), "container")
    descriptor: TaskDescriptor = _FixtureTaskDescriptor(
        type=OpenIdentifier("fixture.request"),
        version="1.0",
        input_schema_id=None,
        output_schema_id=None,
        metadata=_EMPTY_EXTENSIONS,
        extensions=_EMPTY_EXTENSIONS,
    )
    # The open task is intentionally minimal: its only purpose is to cross normal
    # ModelRequest validation while keeping output facts owned by the response.
    task: ModelTaskRequest = _FixtureRequestTask(
        descriptor=descriptor,
        document=TaskDocument("1.0", TaskGroupNode("request-root", kind, ())),
        artifacts=ArtifactCatalog(),
        metadata=_EMPTY_EXTENSIONS,
        extensions=_EMPTY_EXTENSIONS,
    )
    return ModelRequestBuilder(target, task).build()


def _output_from_json(document: dict[str, JsonValue]) -> ModelOutput:
    """Reconstruct one fixture output through response validation and Runtime."""
    target = _decode_target(document.get("target"))
    resolved_value = document.get("resolvedModel")
    resolved_model = (
        None
        if resolved_value is None
        else _decode_model(
            _require_object(resolved_value, "output.resolvedModel"),
            "output.resolvedModel",
        )
    )
    status = OutputStatus(
        OpenIdentifier(_require_string(document.get("status"), "output.status"))
    )
    states = tuple(
        _decode_protocol_state(item)
        for item in _require_array(
            document.get("protocolState"), "output.protocolState"
        )
    )
    response = ParsedTaskResponse(
        result=_decode_result(document.get("result")),
        status=status,
        resolved_model=resolved_model,
        stop_reason=_optional_string(document.get("stopReason"), "output.stopReason"),
        usage=_decode_usage(document.get("usage")),
        protocol_state=states,
        extensions=_mapping_or_empty(document, "extensions"),
    )
    diagnostics = tuple(
        _decode_diagnostic(item)
        for item in _require_array(document.get("diagnostics"), "output.diagnostics")
    )
    # Runtime is the only production owner allowed to combine the original target,
    # parsed service facts, and Runtime diagnostics into a top-level ModelOutput.
    return ModelOutputAssembler().assemble(
        _request_for_target(target),
        response,
        diagnostics,
        output_id=_optional_string(document.get("id"), "output.id"),
    )


def _serialize_model(model: ModelDescriptor) -> dict[str, JsonValue]:
    """Serialize one model descriptor without adding absent optional facts."""
    document: dict[str, JsonValue] = {"name": model.name}
    # Each optional field is independent; exact presence is part of the output
    # ownership contract and cannot be inferred from name, target, or family.
    if model.display_name is not None:
        document["displayName"] = model.display_name
    if model.family is not None:
        document["family"] = model.family.value
    if model.version is not None:
        document["version"] = model.version
    if model.description is not None:
        document["description"] = model.description
    if model.metadata:
        document["metadata"] = dict(model.metadata)
    if model.extensions:
        document["extensions"] = dict(model.extensions)
    return document


def _serialize_target(target: ModelTarget) -> dict[str, JsonValue]:
    """Serialize the request-owned target without access or response data."""
    document: dict[str, JsonValue] = {
        "serviceId": target.service_id.value,
        "protocolId": target.protocol_id.value,
        "model": _serialize_model(target.model),
    }
    # Optional deployment and target extensions are emitted only when they were
    # present, preserving omission separately from explicit response properties.
    if target.deployment_id is not None:
        document["deploymentId"] = target.deployment_id
    if target.extensions:
        document["extensions"] = dict(target.extensions)
    return document


def _serialize_message_element(element: MessageElement) -> dict[str, JsonValue]:
    """Serialize one result message element while retaining every array order."""
    document: dict[str, JsonValue] = {
        "id": element.id,
        "kind": {
            "id": element.kind.id.value,
            "category": element.kind.category,
            "composition": element.kind.composition,
        },
        "subElements": [
            _serialize_message_element(child) for child in element.sub_elements
        ],
    }
    if isinstance(element, MessageEntry):
        # Entry content remains separate from tree children. Text payloads retain
        # their exact segment ordering and decomposed Unicode code points.
        role: dict[str, JsonValue] = {"id": element.role.id.value}
        if element.role.semantic is not None:
            role["semantic"] = element.role.semantic
        if element.role.raw_value is not None:
            role["rawValue"] = element.role.raw_value
        if element.role.extensions:
            role["extensions"] = dict(element.role.extensions)
        document["role"] = role
        document["content"] = [
            {
                "id": content.id,
                "kind": {"id": content.kind.id.value},
                "text": content.text,
                **({"metadata": dict(content.metadata)} if content.metadata else {}),
                **(
                    {"extensions": dict(content.extensions)}
                    if content.extensions
                    else {}
                ),
            }
            for content in cast(tuple[TextMessageContent, ...], element.content)
        ]
    else:
        # This fixture intentionally uses no generic name, attributes, value, or
        # relations; fail if reconstruction unexpectedly creates such information.
        if element.name is not None:
            document["name"] = element.name
        if element.attributes:
            document["attributes"] = dict(element.attributes)
        if element.value is not None:
            document["value"] = element.value
    if element.relations:
        document["relations"] = [
            {
                "source": relation.source,
                "target": relation.target,
                "type": relation.type.value,
                **({"metadata": dict(relation.metadata)} if relation.metadata else {}),
            }
            for relation in element.relations
        ]
    if element.metadata:
        document["metadata"] = dict(element.metadata)
    if element.extensions:
        document["extensions"] = dict(element.extensions)
    return document


def _serialize_messages(messages: MessageDocument) -> dict[str, JsonValue]:
    """Serialize one independent output MessageDocument exactly."""
    document: dict[str, JsonValue] = {
        "version": messages.version,
        "purpose": messages.purpose,
        "root": _serialize_message_element(messages.root),
    }
    # Non-empty preservation channels stay on MessageDocument rather than being
    # promoted to task result or top-level output extensions.
    if messages.metadata:
        document["metadata"] = dict(messages.metadata)
    if messages.extensions:
        document["extensions"] = dict(messages.extensions)
    return document


def _serialize_result(result: ConversationTaskResult) -> dict[str, JsonValue]:
    """Serialize the concrete result through its generated canonical task tree."""
    root = result.document.root
    if len(root.children) != 1:
        raise AssertionError("ConversationTaskResult must contain one result node.")
    node = root.children[0]
    # The private node's message surface is intentionally accessed structurally;
    # its concrete implementation remains internal to ConversationTaskResult.
    if not isinstance(node, _FixtureMessageCarrier):
        raise AssertionError("Conversation result node must carry messages.")
    messages = node.messages
    document: dict[str, JsonValue] = {
        "descriptor": {"type": result.descriptor.type.value},
        "document": {
            "version": result.document.version,
            "root": {
                "id": root.id,
                "kind": {
                    "id": root.kind.id.value,
                    "composition": root.kind.composition,
                },
                "children": [
                    {
                        "id": node.id,
                        "kind": {
                            "id": node.kind.id.value,
                            "composition": node.kind.composition,
                        },
                        "children": [],
                        "messages": _serialize_messages(messages),
                    }
                ],
            },
        },
        "artifacts": {"artifacts": []},
    }
    # Result metadata and extensions remain distinct from the nested TaskDocument
    # and MessageDocument channels during the complete round trip.
    if result.metadata:
        document["metadata"] = dict(result.metadata)
    if result.extensions:
        document["extensions"] = dict(result.extensions)
    return document


def _serialize_usage(usage: TokenUsage) -> dict[str, JsonValue]:
    """Serialize present usage counts independently and without arithmetic."""
    document: dict[str, JsonValue] = {}
    # Missing counts remain omitted, explicit zeros remain numbers, and total is
    # never recomputed even when all three standard values are present.
    if usage.input_tokens is not None:
        document["inputTokens"] = usage.input_tokens
    if usage.output_tokens is not None:
        document["outputTokens"] = usage.output_tokens
    if usage.total_tokens is not None:
        document["totalTokens"] = usage.total_tokens
    if usage.extensions:
        document["extensions"] = dict(usage.extensions)
    return document


def _serialize_diagnostic(diagnostic: Diagnostic) -> dict[str, JsonValue]:
    """Serialize one Runtime diagnostic without creating absent optionals."""
    document: dict[str, JsonValue] = {
        "code": diagnostic.code,
        "severity": diagnostic.severity,
        "phase": diagnostic.phase.id.value,
        "message": diagnostic.message,
    }
    # Optional location, service, and details stay independently absent instead of
    # being filled from output target, protocol state, or response extensions.
    if diagnostic.path is not None:
        document["path"] = diagnostic.path
    if diagnostic.service_id is not None:
        document["serviceId"] = diagnostic.service_id.value
    if diagnostic.details is not None:
        document["details"] = diagnostic.details
    return document


def _serialize_output(output: ModelOutput) -> dict[str, JsonValue]:
    """Serialize exactly the assembled ModelOutput field ownership boundary."""
    if not isinstance(output.result, ConversationTaskResult):
        raise AssertionError("Fixture output must contain ConversationTaskResult.")
    document: dict[str, JsonValue] = {
        "target": _serialize_target(output.target),
        "status": output.status.id.value,
        "result": _serialize_result(output.result),
        "diagnostics": [
            _serialize_diagnostic(diagnostic) for diagnostic in output.diagnostics
        ],
        "protocolState": [
            {
                "serviceId": state.service_id.value,
                "protocolId": state.protocol_id.value,
                "stateType": state.state_type.value,
                "stateValue": state.state_value,
            }
            for state in output.protocol_state
        ],
    }
    # Nullable service facts are present in this fixture. Keeping conditional
    # emission makes the helper faithful to domain absence rather than fixture-only
    # assumptions and prevents target model fallback for resolvedModel.
    if output.id is not None:
        document["id"] = output.id
    if output.resolved_model is not None:
        document["resolvedModel"] = _serialize_model(output.resolved_model)
    if output.stop_reason is not None:
        document["stopReason"] = output.stop_reason
    if output.usage is not None:
        document["usage"] = _serialize_usage(output.usage)
    if output.extensions:
        document["extensions"] = dict(output.extensions)
    return document


def _adapter() -> SchemaValidatorAdapter:
    """Load the registered standalone ModelOutput schema."""
    schema = _load_object(_SCHEMA_PATH)
    # No companion registration is permitted here; successful validation proves
    # the result, Message, Artifact, target, and output definitions are embedded.
    assert schema.get("$id") == _SCHEMA_ID.value
    return SchemaValidatorAdapter(SchemaLoader({_SCHEMA_ID: schema}))


def _fixture_case() -> dict[str, JsonValue]:
    """Return the fixture's one uniquely named conversation result case."""
    fixture = _load_object(_FIXTURE_PATH)
    cases = _require_array(fixture.get("cases"), "cases")
    matches = [
        _require_object(case, "cases[]")
        for case in cases
        if isinstance(case, dict) and case.get("name") == _CASE_NAME
    ]
    # Missing or duplicate names would make selection platform- or order-dependent
    # and therefore cannot become stable cross-language conformance evidence.
    if len(matches) != 1:
        raise AssertionError(f"Expected exactly one case named {_CASE_NAME!r}.")
    return matches[0]


def _string_array(value: JsonValue | None, field_name: str) -> tuple[str, ...]:
    """Decode one expected string array into an immutable ordered tuple."""
    values = _require_array(value, field_name)
    # Index-specific field paths keep malformed expected values attributable to
    # their precise location without coercing them for comparison.
    return tuple(
        _require_string(item, f"{field_name}[{index}]")
        for index, item in enumerate(values)
    )


def _message_preorder(root: MessageElement) -> tuple[MessageElement, ...]:
    """Return all result message elements in deterministic document preorder."""
    ordered: list[MessageElement] = []
    pending: list[MessageElement] = [root]
    # Reverse child pushes retain left-to-right declaration order when the LIFO
    # stack consumes the next element, avoiding recursion depth dependence.
    while pending:
        element = pending.pop()
        ordered.append(element)
        pending.extend(reversed(element.sub_elements))
    return tuple(ordered)


def test_conversation_result_fixture_is_registered_and_well_formed() -> None:
    """Verify discovery metadata, envelope membership, and case identity."""
    index = _load_object(_INDEX_PATH)
    fixture = _load_object(_FIXTURE_PATH)
    resources = _require_array(index.get("resources"), "resources")
    cases = _require_array(fixture.get("cases"), "cases")

    # Exact envelope membership makes future format changes explicit instead of
    # allowing individual platforms to ignore undeclared top-level information.
    assert _FIXTURE_PATH.name in resources
    assert frozenset(fixture) == frozenset(("cases", "format_version", "schemaId"))
    assert fixture["format_version"] == 1
    assert fixture["schemaId"] == _SCHEMA_ID.value
    names = tuple(
        _require_string(_require_object(case, "cases[]").get("name"), "case.name")
        for case in cases
    )
    assert names == (_CASE_NAME,)


def test_conversation_result_fixture_matches_schema_runtime_and_round_trip() -> None:
    """Verify Schema, domain validation, Runtime assembly, and exact round trip."""
    case = _fixture_case()
    output_document = _require_object(case.get("output"), "case.output")

    # Schema validates the language-neutral representation first. Reconstruction
    # then crosses public domain constructors, response Validator, request Builder,
    # and Runtime's only ModelOutput construction path before exact serialization.
    assert _adapter().validate(_SCHEMA_ID, output_document) == ()
    output = _output_from_json(output_document)
    assert isinstance(output, ModelOutput)
    assert json_fixtures_equal(_serialize_output(output), output_document)


def test_conversation_result_fixture_preserves_text_and_message_order() -> None:
    """Verify assistant projection, Unicode, roles, elements, and content order."""
    case = _fixture_case()
    expected = _require_object(case.get("expected"), "case.expected")
    output = _output_from_json(_require_object(case.get("output"), "case.output"))
    if not isinstance(output.result, ConversationTaskResult):
        raise AssertionError("Fixture result must be ConversationTaskResult.")

    elements = _message_preorder(output.result.messages.root)
    entries = tuple(
        element for element in elements if isinstance(element, MessageEntry)
    )
    contents = tuple(
        cast(TextMessageContent, content)
        for entry in entries
        for content in entry.content
    )
    assert tuple(element.id for element in elements) == _string_array(
        expected.get("messageElementOrder"), "expected.messageElementOrder"
    )
    assert tuple(entry.role.id.value for entry in entries) == _string_array(
        expected.get("roleOrder"), "expected.roleOrder"
    )
    assert tuple(content.id for content in contents) == _string_array(
        expected.get("contentOrder"), "expected.contentOrder"
    )

    # Projection includes only assistant text in preorder and content tuple order.
    # The user segment proves role filtering, while decomposed e + combining acute
    # proves no normalization occurs in parsing, projection, or serialization.
    assistant_segments = tuple(
        content.text
        for entry in entries
        if entry.role.id == OpenIdentifier("message.assistant")
        for content in cast(tuple[TextMessageContent, ...], entry.content)
    )
    assert assistant_segments == _string_array(
        expected.get("assistantTextSegments"), "expected.assistantTextSegments"
    )
    expected_text = _require_string(
        expected.get("projectedText"), "expected.projectedText"
    )
    assert output.result.text == expected_text == "".join(assistant_segments)
    assert unicodedata.normalize("NFC", expected_text) != expected_text


def test_conversation_result_fixture_preserves_completion_facts() -> None:
    """Verify status, stop reason, and every usage value stay independent."""
    case = _fixture_case()
    expected = _require_object(case.get("expected"), "case.expected")
    output = _output_from_json(_require_object(case.get("output"), "case.output"))

    # Status and stopReason remain opaque provider facts. Usage retains reported
    # fields exactly and does not compute total or discard provider extensions.
    assert output.status.id.value == _require_string(
        expected.get("status"), "expected.status"
    )
    assert output.stop_reason == _require_string(
        expected.get("stopReason"), "expected.stopReason"
    )
    if output.usage is None:
        raise AssertionError("Fixture output usage must be present.")
    assert json_fixtures_equal(
        _serialize_usage(output.usage),
        _require_object(expected.get("usage"), "expected.usage"),
    )
    assert output.usage.input_tokens == 37
    assert output.usage.output_tokens == 12
    assert output.usage.total_tokens == 49


def test_conversation_result_fixture_preserves_runtime_and_protocol_order() -> None:
    """Verify Runtime diagnostics and protocol state retain separate ordering."""
    case = _fixture_case()
    expected = _require_object(case.get("expected"), "case.expected")
    output = _output_from_json(_require_object(case.get("output"), "case.output"))

    # Diagnostics are Runtime-owned while state is adapter-owned. Comparing each
    # sequence independently detects accidental merging, sorting, or source swaps.
    assert tuple(diagnostic.code for diagnostic in output.diagnostics) == _string_array(
        expected.get("diagnosticOrder"), "expected.diagnosticOrder"
    )
    assert tuple(state.state_type.value for state in output.protocol_state) == (
        _string_array(expected.get("protocolStateOrder"), "expected.protocolStateOrder")
    )
    assert output.target.model.name == "fixture-model"
    assert output.resolved_model is not None
    assert output.resolved_model.name == "fixture-model-resolved"
