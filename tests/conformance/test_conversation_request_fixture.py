"""Conformance checks for the language-neutral Conversation Request fixture."""

from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Literal, cast

from mconet.core.domain import (
    ArtifactCatalog,
    ConversationInputNode,
    ConversationTaskBuilder,
    ConversationTaskRequest,
    Extensions,
    GenerationParameters,
    GenerationParametersNode,
    JsonValue,
    MessageDocument,
    MessageDocumentBuilder,
    MessageElement,
    MessageElementKind,
    MessageEntry,
    MessageEntryBuilder,
    MessageGroup,
    MessageRelation,
    MessageRole,
    ModelDescriptor,
    ModelRequest,
    ModelRequestBuilder,
    ModelTarget,
    NamedModel,
    OpenIdentifier,
    TaskDocument,
    TaskGroupNode,
    TaskNode,
    TextMessageContent,
    validate_message_group,
    validate_model_request,
)
from mconet.testing import (
    SchemaLoader,
    SchemaValidatorAdapter,
    json_fixtures_equal,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_FIXTURE_ROOT = _PROJECT_ROOT / "spec" / "fixtures" / "r1-text-unary"
_FIXTURE_PATH = _FIXTURE_ROOT / "conversation-request.json"
_MESSAGE_FIXTURE_PATH = _FIXTURE_ROOT / "message-document.json"
_INDEX_PATH = _FIXTURE_ROOT / "index.json"
_SCHEMA_PATH = _PROJECT_ROOT / "spec" / "schemas" / "model-request.json"
_SCHEMA_ID = OpenIdentifier("schema.model_request")
_EMPTY_EXTENSIONS: Extensions = MappingProxyType({})


def _empty_extensions() -> Extensions:
    """Return immutable empty data for omitted fixture mapping channels."""
    # No nested state exists in the shared proxy, so omitted mappings can reuse
    # it without allowing reconstructed requests to affect one another.
    return _EMPTY_EXTENSIONS


@dataclass(frozen=True, slots=True)
class _FixtureMessageKind:
    """Represent one open message element Kind decoded from JSON."""

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


@dataclass(frozen=True, slots=True)
class _FixtureTaskKind:
    """Represent one open task node Kind decoded from JSON."""

    id: OpenIdentifier
    """Portable task Kind identity."""

    composition: Literal["leaf", "container"]
    """Leaf or container composition retained from the fixture."""


@dataclass(frozen=True, slots=True)
class _FixtureTarget:
    """Provide a complete structural ModelTarget reconstructed from JSON."""

    service_id: OpenIdentifier
    """Selected service identity."""

    protocol_id: OpenIdentifier
    """Selected protocol identity."""

    model: ModelDescriptor
    """Requested model descriptor."""

    deployment_id: str | None
    """Optional service deployment identity."""

    extensions: Extensions
    """Unknown target data retained from the fixture."""


def _load_object(path: Path) -> dict[str, JsonValue]:
    """Load one committed UTF-8 JSON document and require an object root."""
    document: JsonValue = json.loads(path.read_text(encoding="utf-8"))
    # Golden resources use named envelopes. Rejecting scalar or array roots keeps
    # fixture interpretation identical across languages before reconstruction.
    if not isinstance(document, dict):
        raise AssertionError(f"Expected a JSON object in {path}.")
    return document


def _require_object(value: JsonValue | None, field_name: str) -> dict[str, JsonValue]:
    """Return one required object-valued fixture field."""
    # Reject absent, null, scalar, and array values before any domain constructor
    # can apply host-language casts or produce a less precise diagnostic.
    if not isinstance(value, dict):
        raise AssertionError(f"{field_name} must be a JSON object.")
    return value


def _require_array(value: JsonValue | None, field_name: str) -> list[JsonValue]:
    """Return one required array-valued fixture field in source order."""
    # Array order is conformance evidence for TaskNode, MessageElement, content,
    # stop sequence, and case membership; never convert it to a set or mapping.
    if not isinstance(value, list):
        raise AssertionError(f"{field_name} must be a JSON array.")
    return value


def _require_string(value: JsonValue | None, field_name: str) -> str:
    """Return one required JSON string without coercion."""
    # Numeric, boolean, null, and composite values cannot be stringified because
    # that would let platforms produce different identifiers or text data.
    if not isinstance(value, str):
        raise AssertionError(f"{field_name} must be a JSON string.")
    return value


def _optional_string(value: JsonValue | None, field_name: str) -> str | None:
    """Return an optional nullable string while rejecting other JSON kinds."""
    # Missing and explicit null share the domain None representation. Present
    # strings remain exact and are never trimmed, normalized, or case-folded.
    if value is not None and not isinstance(value, str):
        raise AssertionError(f"{field_name} must be a JSON string or null.")
    return value


def _require_number(value: JsonValue | None, field_name: str) -> int | float:
    """Return one required exact JSON number while excluding booleans."""
    # Python bool is an integer subclass, so exact type membership is required to
    # preserve JSON boolean and number as different portable value categories.
    if type(value) not in (int, float):
        raise AssertionError(f"{field_name} must be a JSON number.")
    return cast(int | float, value)


def _require_integer(value: JsonValue | None, field_name: str) -> int:
    """Return one required exact JSON integer while excluding booleans."""
    # Token and seed fields cannot accept floats or booleans even when their host
    # values compare equal to an integer on a particular platform.
    if type(value) is not int:
        raise AssertionError(f"{field_name} must be a JSON integer.")
    return value


def _mapping_or_empty(document: dict[str, JsonValue], field_name: str) -> Extensions:
    """Decode an omitted JSON object channel as immutable empty data."""
    # Present mappings remain uninterpreted until the public composed Validators
    # enforce recursive JsonValue and portable-number semantics.
    if field_name not in document:
        return _EMPTY_EXTENSIONS
    return _require_object(document[field_name], field_name)


def _decode_message_kind(value: JsonValue | None) -> _FixtureMessageKind:
    """Decode one complete MessageElement Kind without inference."""
    document = _require_object(value, "message.kind")
    composition = _require_string(
        document.get("composition"), "message.kind.composition"
    )
    # Schema validation already narrows composition, while this guard prevents
    # direct helper calls from bypassing the Literal domain contract.
    if composition not in ("leaf", "container"):
        raise AssertionError("message.kind.composition must be leaf or container.")
    return _FixtureMessageKind(
        OpenIdentifier(_require_string(document.get("id"), "message.kind.id")),
        _require_string(document.get("category"), "message.kind.category"),
        composition,
    )


def _decode_message_role(value: JsonValue | None) -> MessageRole:
    """Decode one role while preserving open identity and optional data."""
    document = _require_object(value, "message.role")
    # A structural role avoids known-value enum mapping, so future identities
    # retain their raw and semantic data through the same request path.
    return _FixtureMessageRole(
        id=OpenIdentifier(_require_string(document.get("id"), "message.role.id")),
        semantic=_optional_string(document.get("semantic"), "message.role.semantic"),
        raw_value=_optional_string(document.get("rawValue"), "message.role.rawValue"),
        extensions=_mapping_or_empty(document, "extensions"),
    )


def _decode_message_relation(value: JsonValue) -> MessageRelation:
    """Decode one directed message relation without resolving endpoints early."""
    document = _require_object(value, "message.relation")
    # Complete document validation resolves forward targets only after every
    # ordered element has been reconstructed and indexed.
    return MessageRelation(
        source=_require_string(document.get("source"), "relation.source"),
        target=_require_string(document.get("target"), "relation.target"),
        type=OpenIdentifier(_require_string(document.get("type"), "relation.type")),
        metadata=_mapping_or_empty(document, "metadata"),
    )


def _decode_message_relations(
    document: dict[str, JsonValue],
) -> tuple[MessageRelation, ...]:
    """Decode an optional relation array in exact declaration order."""
    if "relations" not in document:
        return ()
    values = _require_array(document["relations"], "message.relations")
    # Tuple construction freezes the exact source order before it enters an
    # immutable MessageEntry or MessageGroup.
    return tuple(_decode_message_relation(value) for value in values)


def _decode_text_content(value: JsonValue) -> TextMessageContent:
    """Decode one concrete text content item without Unicode normalization."""
    document = _require_object(value, "message.content")
    kind = _require_object(document.get("kind"), "message.content.kind")
    kind_id = _require_string(kind.get("id"), "message.content.kind.id")
    # The current text-only profile admits only concrete TextMessageContent. Role
    # openness does not weaken this independently owned content scope.
    if kind_id != "content.text":
        raise AssertionError("Conversation Request content must use content.text.")
    return TextMessageContent(
        id=_require_string(document.get("id"), "message.content.id"),
        text=_require_string(document.get("text"), "message.content.text"),
        metadata=_mapping_or_empty(document, "metadata"),
        extensions=_mapping_or_empty(document, "extensions"),
    )


def _decode_message_element(value: JsonValue) -> MessageElement:
    """Reconstruct one entry or group while preserving every array order."""
    document = _require_object(value, "message.element")
    element_id = _require_string(document.get("id"), "message.element.id")
    kind = _decode_message_kind(document.get("kind"))
    child_values = _require_array(
        document.get("subElements"), "message.element.subElements"
    )

    if kind.id.value == "message.entry":
        # EntryBuilder exercises the supported user construction path and retains
        # content and relation insertion order without a parallel history model.
        if child_values:
            raise AssertionError("MessageEntry subElements must remain empty.")
        builder = MessageEntryBuilder(
            element_id, _decode_message_role(document.get("role"))
        )
        for content in _require_array(document.get("content"), "message.content"):
            builder.add_content(_decode_text_content(content))
        for relation in _decode_message_relations(document):
            builder.add_relation(relation)
        builder.with_metadata(_mapping_or_empty(document, "metadata"))
        builder.with_extensions(_mapping_or_empty(document, "extensions"))
        return builder.build()

    if kind.composition != "container":
        raise AssertionError("Conversation Request non-entry messages are containers.")
    # Recursively decode child arrays before constructing their owning group; tuple
    # order exactly follows the language-neutral JSON source.
    group = MessageGroup(
        id=element_id,
        kind=kind,
        sub_elements=tuple(_decode_message_element(child) for child in child_values),
        name=_optional_string(document.get("name"), "message.element.name"),
        attributes=_mapping_or_empty(document, "attributes"),
        value=document.get("value"),
        relations=_decode_message_relations(document),
        metadata=_mapping_or_empty(document, "metadata"),
        extensions=_mapping_or_empty(document, "extensions"),
    )
    return validate_message_group(group)


def _decode_message_document(document: dict[str, JsonValue]) -> MessageDocument:
    """Reconstruct one complete input document through the public Builder."""
    root = _decode_message_element(document.get("root"))
    if not isinstance(root, MessageGroup):
        raise AssertionError("MessageDocument root must decode as a MessageGroup.")
    purpose = _require_string(document.get("purpose"), "messages.purpose")
    if purpose not in ("input", "output", "context", "custom"):
        raise AssertionError("messages.purpose must be a declared purpose.")

    # DocumentBuilder performs global ID and relation validation after the exact
    # immutable element tree has been constructed.
    return (
        MessageDocumentBuilder(
            _require_string(document.get("version"), "messages.version"),
            purpose,
            root,
        )
        .with_metadata(_mapping_or_empty(document, "metadata"))
        .with_extensions(_mapping_or_empty(document, "extensions"))
        .build()
    )


def _decode_task_kind(value: JsonValue | None) -> _FixtureTaskKind:
    """Decode one complete TaskNode Kind without deriving composition."""
    document = _require_object(value, "task.kind")
    composition = _require_string(document.get("composition"), "task.composition")
    # Keep open ID and composition as separate fields; Kind spelling must not
    # silently choose leaf/container behavior during fixture reconstruction.
    if composition not in ("leaf", "container"):
        raise AssertionError("task.kind.composition must be leaf or container.")
    return _FixtureTaskKind(
        OpenIdentifier(_require_string(document.get("id"), "task.kind.id")),
        composition,
    )


def _decode_generation_parameters(
    document: dict[str, JsonValue],
) -> GenerationParameters:
    """Decode every present generation control without inference or reordering."""
    stop_values = _require_array(document.get("stop"), "parameters.stop")
    stop: list[str] = []
    for index, value in enumerate(stop_values):
        # Each string remains exact, including Unicode and punctuation; list order
        # becomes the immutable stop tuple used by the task configuration node.
        stop.append(_require_string(value, f"parameters.stop[{index}]"))
    return GenerationParameters(
        temperature=_require_number(document.get("temperature"), "temperature"),
        top_p=_require_number(document.get("topP"), "topP"),
        max_output_tokens=_require_integer(
            document.get("maxOutputTokens"), "maxOutputTokens"
        ),
        stop=tuple(stop),
        seed=_require_integer(document.get("seed"), "seed"),
    )


def _decode_task_document(document: dict[str, JsonValue]) -> TaskDocument:
    """Reconstruct the ordered conversation task tree from one fixture request."""
    root_document = _require_object(document.get("root"), "task.document.root")
    nodes: list[TaskNode] = []
    for value in _require_array(root_document.get("children"), "task.children"):
        node = _require_object(value, "task.child")
        node_id = _require_string(node.get("id"), "task.child.id")
        kind = _decode_task_kind(node.get("kind"))
        children = _require_array(node.get("children"), "task.child.children")
        if children:
            raise AssertionError(
                "Conversation Fixture standard leaves have no children."
            )

        # Standard Kind identity selects the matching concrete node type; payload
        # fields remain owned by that type and never become generic JsonValue.
        if kind.id.value == "task.input":
            messages = _decode_message_document(
                _require_object(node.get("messages"), "task.input.messages")
            )
            nodes.append(
                ConversationInputNode(
                    node_id,
                    messages,
                    metadata=_mapping_or_empty(node, "metadata"),
                    extensions=_mapping_or_empty(node, "extensions"),
                )
            )
            continue
        if kind.id.value == "task.configuration":
            parameters = _decode_generation_parameters(
                _require_object(node.get("parameters"), "task.parameters")
            )
            nodes.append(
                GenerationParametersNode(
                    node_id,
                    parameters,
                    metadata=_mapping_or_empty(node, "metadata"),
                    extensions=_mapping_or_empty(node, "extensions"),
                )
            )
            continue
        raise AssertionError(f"Unsupported Conversation Fixture node: {kind.id.value}.")

    root = TaskGroupNode(
        id=_require_string(root_document.get("id"), "task.root.id"),
        kind=_decode_task_kind(root_document.get("kind")),
        children=tuple(nodes),
        metadata=_mapping_or_empty(root_document, "metadata"),
        extensions=_mapping_or_empty(root_document, "extensions"),
    )
    # TaskDocument construction preserves exact node order; the Task Builder will
    # later run complete conversation cardinality and payload validation.
    return TaskDocument(
        _require_string(document.get("version"), "task.document.version"),
        root,
        metadata=_mapping_or_empty(document, "metadata"),
        extensions=_mapping_or_empty(document, "extensions"),
    )


def _decode_target(document: dict[str, JsonValue]) -> ModelTarget:
    """Reconstruct one request target while keeping routing dimensions separate."""
    model_document = _require_object(document.get("model"), "target.model")
    family_value = model_document.get("family")
    family = (
        None
        if family_value is None
        else OpenIdentifier(_require_string(family_value, "target.model.family"))
    )
    model: ModelDescriptor = NamedModel(
        name=_require_string(model_document.get("name"), "target.model.name"),
        display_name=_optional_string(
            model_document.get("displayName"), "target.model.displayName"
        ),
        family=family,
        version=_optional_string(model_document.get("version"), "target.model.version"),
        description=_optional_string(
            model_document.get("description"), "target.model.description"
        ),
        metadata=_mapping_or_empty(model_document, "metadata"),
        extensions=_mapping_or_empty(model_document, "extensions"),
    )
    # Target carries no endpoint or authorization; only request routing and its
    # explicit forward-compatible extension channel are reconstructed.
    return _FixtureTarget(
        service_id=OpenIdentifier(
            _require_string(document.get("serviceId"), "target.serviceId")
        ),
        protocol_id=OpenIdentifier(
            _require_string(document.get("protocolId"), "target.protocolId")
        ),
        model=model,
        deployment_id=_optional_string(
            document.get("deploymentId"), "target.deploymentId"
        ),
        extensions=_mapping_or_empty(document, "extensions"),
    )


def _request_from_json(document: dict[str, JsonValue]) -> ModelRequest:
    """Reconstruct and validate one fixture request through both public Builders."""
    task_document = _require_object(document.get("task"), "request.task")
    artifacts = _require_object(task_document.get("artifacts"), "task.artifacts")
    artifact_values = _require_array(artifacts.get("artifacts"), "artifacts")
    # The current conversation profile is artifact-free; an explicit empty
    # catalog remains required and never becomes None or an implicit global scope.
    if artifact_values:
        raise AssertionError("Conversation Request Fixture artifacts must be empty.")

    task = (
        ConversationTaskBuilder(
            _decode_task_document(
                _require_object(task_document.get("document"), "task.document")
            )
        )
        .with_artifacts(ArtifactCatalog())
        .with_metadata(_mapping_or_empty(task_document, "metadata"))
        .with_extensions(_mapping_or_empty(task_document, "extensions"))
        .build()
    )
    target = _decode_target(_require_object(document.get("target"), "request.target"))
    request = (
        ModelRequestBuilder(target, task)
        .with_metadata(_mapping_or_empty(document, "metadata"))
        .with_extensions(_mapping_or_empty(document, "extensions"))
        .build()
    )
    # The composed Validator remains the sole semantic authority after both
    # Builders preserve their exact nested object identities.
    return validate_model_request(request)


def _serialize_message_kind(kind: MessageElementKind) -> dict[str, JsonValue]:
    """Serialize one MessageElement Kind without normalizing its open ID."""
    # Category and composition remain explicit because neither can be inferred
    # from an otherwise equal provider-defined Kind identifier.
    return {
        "id": kind.id.value,
        "category": kind.category,
        "composition": kind.composition,
    }


def _serialize_message_element(element: MessageElement) -> dict[str, JsonValue]:
    """Serialize one message entry or group while preserving ordered arrays."""
    document: dict[str, JsonValue] = {
        "id": element.id,
        "kind": _serialize_message_kind(element.kind),
        "subElements": [
            _serialize_message_element(child) for child in element.sub_elements
        ],
    }
    if isinstance(element, MessageEntry):
        # Entry content remains an ordered payload array and never becomes generic
        # value or task children during serialization.
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
        if element.name is not None:
            document["name"] = element.name
        if element.attributes:
            document["attributes"] = dict(element.attributes)
        if element.value is not None:
            document["value"] = element.value

    # Relations and JSON channels are omitted only when they equal their portable
    # empty defaults; every present array retains source declaration order.
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


def _serialize_messages(document: MessageDocument) -> dict[str, JsonValue]:
    """Serialize one complete MessageDocument without changing Unicode or order."""
    result: dict[str, JsonValue] = {
        "version": document.version,
        "purpose": document.purpose,
        "root": _serialize_message_element(document.root),
    }
    # Default empty channels remain omitted while non-empty producer data is
    # copied exactly into the language-neutral representation.
    if document.metadata:
        result["metadata"] = dict(document.metadata)
    if document.extensions:
        result["extensions"] = dict(document.extensions)
    return result


def _serialize_parameters(parameters: GenerationParameters) -> dict[str, JsonValue]:
    """Serialize all present generation fields without deriving missing values."""
    result: dict[str, JsonValue] = {}
    # Each field is independently optional; this fixture supplies every field so
    # the emitted object proves exact spelling and value retention across Builders.
    if parameters.temperature is not None:
        result["temperature"] = parameters.temperature
    if parameters.top_p is not None:
        result["topP"] = parameters.top_p
    if parameters.max_output_tokens is not None:
        result["maxOutputTokens"] = parameters.max_output_tokens
    if parameters.stop:
        result["stop"] = list(parameters.stop)
    if parameters.seed is not None:
        result["seed"] = parameters.seed
    return result


def _serialize_task_node(node: TaskNode) -> dict[str, JsonValue]:
    """Serialize one supported concrete request node with common fields."""
    document: dict[str, JsonValue] = {
        "id": node.id,
        "kind": {"id": node.kind.id.value, "composition": node.kind.composition},
        "children": [_serialize_task_node(child) for child in node.children],
    }
    # Concrete payload ownership selects one exact field; no generic payload map
    # or Message/parameter cross-projection is introduced.
    if isinstance(node, ConversationInputNode):
        document["messages"] = _serialize_messages(node.messages)
    elif isinstance(node, GenerationParametersNode):
        document["parameters"] = _serialize_parameters(node.parameters)
    elif not isinstance(node, TaskGroupNode):
        raise AssertionError(f"Unsupported fixture TaskNode: {type(node).__name__}.")

    if node.metadata:
        document["metadata"] = dict(node.metadata)
    if node.extensions:
        document["extensions"] = dict(node.extensions)
    return document


def _serialize_task(request: ConversationTaskRequest) -> dict[str, JsonValue]:
    """Serialize one built conversation task using only ModelTaskRequest fields."""
    document: dict[str, JsonValue] = {
        "descriptor": {"type": request.descriptor.type.value},
        "document": {
            "version": request.document.version,
            "root": _serialize_task_node(request.document.root),
        },
        "artifacts": {"artifacts": []},
    }
    # TaskDocument and task request preservation channels remain at their own
    # boundaries and are omitted only when equal to empty defaults.
    if request.document.metadata:
        cast(dict[str, JsonValue], document["document"])["metadata"] = dict(
            request.document.metadata
        )
    if request.document.extensions:
        cast(dict[str, JsonValue], document["document"])["extensions"] = dict(
            request.document.extensions
        )
    if request.metadata:
        document["metadata"] = dict(request.metadata)
    if request.extensions:
        document["extensions"] = dict(request.extensions)
    return document


def _serialize_target(target: ModelTarget) -> dict[str, JsonValue]:
    """Serialize target and model fields without adding access configuration."""
    model: dict[str, JsonValue] = {"name": target.model.name}
    # Optional ModelDescriptor fields remain independent and are emitted only
    # when explicitly present in the fixture-derived domain value.
    if target.model.display_name is not None:
        model["displayName"] = target.model.display_name
    if target.model.family is not None:
        model["family"] = target.model.family.value
    if target.model.version is not None:
        model["version"] = target.model.version
    if target.model.description is not None:
        model["description"] = target.model.description
    if target.model.metadata:
        model["metadata"] = dict(target.model.metadata)
    if target.model.extensions:
        model["extensions"] = dict(target.model.extensions)

    document: dict[str, JsonValue] = {
        "serviceId": target.service_id.value,
        "protocolId": target.protocol_id.value,
        "model": model,
    }
    if target.deployment_id is not None:
        document["deploymentId"] = target.deployment_id
    if target.extensions:
        document["extensions"] = dict(target.extensions)
    return document


def _serialize_request(request: ModelRequest) -> dict[str, JsonValue]:
    """Serialize one built request through the exact task-neutral field surface."""
    if not isinstance(request.task, ConversationTaskRequest):
        raise AssertionError("Fixture request task must be ConversationTaskRequest.")
    document: dict[str, JsonValue] = {
        "target": _serialize_target(request.target),
        "task": _serialize_task(request.task),
    }
    # Access remains absent rather than becoming a null or synthesized object;
    # request preservation channels retain their own non-empty data.
    if request.service_access is not None:
        raise AssertionError("Conversation Request Fixture access must remain absent.")
    if request.metadata:
        document["metadata"] = dict(request.metadata)
    if request.extensions:
        document["extensions"] = dict(request.extensions)
    return document


def _adapter() -> SchemaValidatorAdapter:
    """Load the registered standalone ModelRequest schema."""
    schema = _load_object(_SCHEMA_PATH)
    # The Fixture-selected identity must match the committed resource before any
    # case can become cross-language conformance evidence.
    assert schema.get("$id") == _SCHEMA_ID.value
    return SchemaValidatorAdapter(SchemaLoader({_SCHEMA_ID: schema}))


def _named_case(cases: list[JsonValue], expected_name: str) -> dict[str, JsonValue]:
    """Select exactly one case by its stable language-neutral name."""
    matches = [
        _require_object(case, "cases[]")
        for case in cases
        if isinstance(case, dict) and case.get("name") == expected_name
    ]
    # Duplicate or missing names would make platform selection order-dependent,
    # so require one exact match rather than returning the first candidate.
    if len(matches) != 1:
        raise AssertionError(f"Expected exactly one case named {expected_name!r}.")
    return matches[0]


def _string_array(value: JsonValue | None, field_name: str) -> tuple[str, ...]:
    """Decode one expected string array into an immutable ordered tuple."""
    values = _require_array(value, field_name)
    # Index-specific names retain precise fixture diagnostics without coercing any
    # non-string expected value into a comparable representation.
    return tuple(
        _require_string(item, f"{field_name}[{index}]")
        for index, item in enumerate(values)
    )


def _message_preorder(root: MessageElement) -> tuple[MessageElement, ...]:
    """Return all message elements in deterministic document preorder."""
    ordered: list[MessageElement] = []
    pending: list[MessageElement] = [root]
    # Reverse child pushes preserve declared left-to-right membership when the
    # LIFO stack next consumes each element.
    while pending:
        element = pending.pop()
        ordered.append(element)
        pending.extend(reversed(element.sub_elements))
    return tuple(ordered)


def test_conversation_request_fixture_is_registered_and_linked() -> None:
    """Verify discovery metadata and source Message fixture linkage are exact."""
    index = _load_object(_INDEX_PATH)
    fixture = _load_object(_FIXTURE_PATH)
    resources = _require_array(index.get("resources"), "resources")
    cases = _require_array(fixture.get("cases"), "cases")

    # Exact envelope membership makes format evolution explicit and prevents a
    # platform from ignoring undeclared case or source-resource fields.
    assert "conversation-request.json" in resources
    assert frozenset(fixture) == frozenset(
        {
            "cases",
            "format_version",
            "messageFixtureResource",
            "schemaId",
        }
    )
    assert fixture["format_version"] == 1
    assert fixture["schemaId"] == _SCHEMA_ID.value
    assert fixture["messageFixtureResource"] == _MESSAGE_FIXTURE_PATH.name
    names = [
        _require_string(_require_object(case, "cases[]").get("name"), "cases[].name")
        for case in cases
    ]
    assert names
    assert len(names) == len(set(names))


def test_conversation_request_fixture_reuses_message_golden_document() -> None:
    """Verify the embedded conversation input is the declared Message Golden case."""
    fixture = _load_object(_FIXTURE_PATH)
    case = _named_case(
        _require_array(fixture.get("cases"), "cases"),
        "ordered-multi-turn-unicode-and-parameters",
    )
    source_name = _require_string(
        case.get("sourceMessageCase"), "case.sourceMessageCase"
    )
    message_fixture = _load_object(_MESSAGE_FIXTURE_PATH)
    source_case = _named_case(
        _require_array(message_fixture.get("validCases"), "validCases"), source_name
    )
    request = _require_object(case.get("request"), "case.request")
    task = _require_object(request.get("task"), "request.task")
    task_document = _require_object(task.get("document"), "task.document")
    root = _require_object(task_document.get("root"), "task.document.root")
    children = _require_array(root.get("children"), "task.document.root.children")
    input_node = _require_object(children[0], "task.input")
    embedded_messages = _require_object(input_node.get("messages"), "task.messages")
    source_messages = _require_object(source_case.get("input"), "message.input")

    # Structural equality proves the request does not copy, flatten, normalize,
    # or partially restate the existing multi-turn Message Golden contract.
    assert json_fixtures_equal(embedded_messages, source_messages)


def test_conversation_request_fixture_matches_schema_and_public_builders() -> None:
    """Verify every request passes Schema, Builders, Validators, and round trip."""
    fixture = _load_object(_FIXTURE_PATH)
    cases = _require_array(fixture.get("cases"), "cases")
    adapter = _adapter()

    for case_value in cases:
        case = _require_object(case_value, "cases[]")
        request_document = _require_object(case.get("request"), "case.request")
        # Schema checks the complete language-neutral representation before domain
        # reconstruction exercises both public Builder and composed Validator paths.
        assert adapter.validate(_SCHEMA_ID, request_document) == ()
        request = _request_from_json(request_document)
        assert isinstance(request, ModelRequest)
        assert isinstance(request.task, ConversationTaskRequest)
        assert json_fixtures_equal(_serialize_request(request), request_document)


def test_conversation_request_fixture_preserves_all_declared_orders() -> None:
    """Verify Task, Message, Role, Content, text, and stop order remain exact."""
    fixture = _load_object(_FIXTURE_PATH)
    case = _named_case(
        _require_array(fixture.get("cases"), "cases"),
        "ordered-multi-turn-unicode-and-parameters",
    )
    expected = _require_object(case.get("expected"), "case.expected")
    request = _request_from_json(_require_object(case.get("request"), "case.request"))
    if not isinstance(request.task, ConversationTaskRequest):
        raise AssertionError("Fixture task must be ConversationTaskRequest.")

    task_nodes = request.task.document.root.children
    assert tuple(node.id for node in task_nodes) == _string_array(
        expected.get("taskNodeOrder"), "expected.taskNodeOrder"
    )
    input_node = task_nodes[0]
    parameters_node = task_nodes[1]
    if not isinstance(input_node, ConversationInputNode) or not isinstance(
        parameters_node, GenerationParametersNode
    ):
        raise AssertionError("Fixture task nodes must retain their concrete types.")

    elements = _message_preorder(input_node.messages.root)
    assert tuple(element.id for element in elements) == _string_array(
        expected.get("messageElementOrder"), "expected.messageElementOrder"
    )
    assert tuple(
        element.id for element in input_node.messages.root.sub_elements
    ) == _string_array(expected.get("messageGroupOrder"), "expected.messageGroupOrder")
    entries = tuple(
        element for element in elements if isinstance(element, MessageEntry)
    )
    assert tuple(entry.id for entry in entries) == _string_array(
        expected.get("messageEntryOrder"), "expected.messageEntryOrder"
    )
    assert tuple(entry.role.id.value for entry in entries) == _string_array(
        expected.get("roleOrder"), "expected.roleOrder"
    )

    # Flatten content only after entry preorder is fixed; this preserves both turn
    # ordering and multiple content segments within one assistant entry.
    contents = tuple(
        cast(TextMessageContent, content)
        for entry in entries
        for content in entry.content
    )
    assert tuple(content.id for content in contents) == _string_array(
        expected.get("contentOrder"), "expected.contentOrder"
    )
    assert tuple(content.text for content in contents) == _string_array(
        expected.get("textOrder"), "expected.textOrder"
    )
    assert parameters_node.parameters.stop == _string_array(
        expected.get("stopOrder"), "expected.stopOrder"
    )

    # The second assistant segment intentionally remains decomposed Unicode, so
    # cross-language implementations cannot normalize while preserving appearance.
    decomposed = contents[3].text
    assert decomposed != unicodedata.normalize("NFC", decomposed)


def test_conversation_request_fixture_preserves_generation_parameter_values() -> None:
    """Verify every generation field remains exact and independent of messages."""
    fixture = _load_object(_FIXTURE_PATH)
    case = _named_case(
        _require_array(fixture.get("cases"), "cases"),
        "ordered-multi-turn-unicode-and-parameters",
    )
    expected = _require_object(case.get("expected"), "case.expected")
    expected_parameters = _require_object(
        expected.get("generationParameters"), "expected.generationParameters"
    )
    request = _request_from_json(_require_object(case.get("request"), "case.request"))
    if not isinstance(request.task, ConversationTaskRequest):
        raise AssertionError("Fixture task must be ConversationTaskRequest.")
    parameter_nodes = tuple(
        node
        for node in request.task.document.root.children
        if isinstance(node, GenerationParametersNode)
    )
    if len(parameter_nodes) != 1:
        raise AssertionError("Fixture must contain exactly one parameter node.")

    # Canonical serialization compares all five controls, including ordered stop
    # values, without deriving fields from the MessageDocument or model target.
    assert json_fixtures_equal(
        _serialize_parameters(parameter_nodes[0].parameters), expected_parameters
    )
