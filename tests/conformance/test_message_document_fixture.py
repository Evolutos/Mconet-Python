"""Conformance checks for language-neutral MessageDocument Golden fixtures."""

from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Literal, cast

from mconet.core.domain import (
    Extensions,
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
    OpenIdentifier,
    TextMessageContent,
    validate_message_group,
)
from mconet.testing import (
    SchemaLoader,
    SchemaValidationIssue,
    SchemaValidatorAdapter,
    json_fixtures_equal,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_FIXTURE_PATH = (
    _PROJECT_ROOT / "spec" / "fixtures" / "r1-text-unary" / "message-document.json"
)
_INDEX_PATH = _FIXTURE_PATH.parent / "index.json"
_SCHEMA_PATH = _PROJECT_ROOT / "spec" / "schemas" / "message-document.json"
_SCHEMA_ID = OpenIdentifier("schema.message_document")
_EMPTY_EXTENSIONS: Extensions = MappingProxyType({})


def _empty_extensions() -> Extensions:
    """Return immutable empty data for omitted fixture mapping channels."""
    # The shared proxy contains no nested values and rejects mutation, so fixture
    # objects can safely reuse it without leaking state between cases.
    return _EMPTY_EXTENSIONS


@dataclass(frozen=True, slots=True)
class _FixtureKind:
    """Represent one open message element Kind decoded from JSON."""

    id: OpenIdentifier
    """Portable standard or provider-defined Kind identity."""

    category: str
    """Producer-defined element classification category."""

    composition: Literal["leaf", "container"]
    """Tree composition retained without inference from Kind identity."""


@dataclass(frozen=True, slots=True)
class _FixtureRole:
    """Represent a standard or provider-defined role decoded from JSON."""

    id: OpenIdentifier
    """Portable role identity retained without a closed known-role table."""

    semantic: str | None = None
    """Optional producer guidance for unknown role semantics."""

    raw_value: str | None = None
    """Optional exact external spelling retained for round trips."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Unknown role fields preserved as portable JSON data."""


def _load_object(path: Path) -> dict[str, JsonValue]:
    """Load one committed UTF-8 JSON document and require an object root."""
    document: JsonValue = json.loads(path.read_text(encoding="utf-8"))
    # Golden resources use named envelopes; accepting arrays or scalars here
    # would let platforms interpret the same file through incompatible shapes.
    if not isinstance(document, dict):
        raise AssertionError(f"Expected a JSON object in {path}.")
    return document


def _require_object(value: JsonValue | None, field_name: str) -> dict[str, JsonValue]:
    """Return one required object-valued fixture field."""
    # Reject missing, null, and non-object values before domain reconstruction
    # performs any language-specific casts or constructor calls.
    if not isinstance(value, dict):
        raise AssertionError(f"{field_name} must be a JSON object.")
    return value


def _require_array(value: JsonValue | None, field_name: str) -> list[JsonValue]:
    """Return one required array-valued fixture field in source order."""
    # Arrays preserve case, element, content, and relation ordering across every
    # implementation; no set or object-key conversion is allowed.
    if not isinstance(value, list):
        raise AssertionError(f"{field_name} must be a JSON array.")
    return value


def _require_string(value: JsonValue | None, field_name: str) -> str:
    """Return one required string without host-language coercion."""
    # Numeric, boolean, null, and composite values cannot be stringified because
    # that would produce different fixture identities across languages.
    if not isinstance(value, str):
        raise AssertionError(f"{field_name} must be a JSON string.")
    return value


def _optional_string(value: JsonValue | None, field_name: str) -> str | None:
    """Return an optional nullable string while rejecting other JSON kinds."""
    # Optional descriptive fields preserve explicit text exactly, while absent
    # and null values both reconstruct to the domain's None representation.
    if value is not None and not isinstance(value, str):
        raise AssertionError(f"{field_name} must be a JSON string or null.")
    return value


def _mapping_or_empty(document: dict[str, JsonValue], field_name: str) -> Extensions:
    """Decode an omitted JSON object channel as immutable empty data."""
    # Present values stay uninterpreted; public validators subsequently apply
    # recursive JsonValue and portable-number semantics.
    if field_name not in document:
        return _EMPTY_EXTENSIONS
    return _require_object(document[field_name], field_name)


def _decode_kind(value: JsonValue | None) -> _FixtureKind:
    """Decode one complete element Kind without deriving any field."""
    document = _require_object(value, "kind")
    composition = _require_string(document.get("composition"), "kind.composition")
    # Schema validation has already narrowed the string, but this explicit guard
    # keeps direct helper misuse from bypassing the Literal domain contract.
    if composition not in ("leaf", "container"):
        raise AssertionError("kind.composition must be leaf or container.")
    return _FixtureKind(
        OpenIdentifier(_require_string(document.get("id"), "kind.id")),
        _require_string(document.get("category"), "kind.category"),
        composition,
    )


def _decode_role(value: JsonValue | None) -> MessageRole:
    """Decode one open role while retaining raw and extension data."""
    document = _require_object(value, "role")
    # Construct a structural role rather than mapping through a known enum so a
    # provider-defined identifier remains exact through public validation.
    return _FixtureRole(
        id=OpenIdentifier(_require_string(document.get("id"), "role.id")),
        semantic=_optional_string(document.get("semantic"), "role.semantic"),
        raw_value=_optional_string(document.get("rawValue"), "role.rawValue"),
        extensions=_mapping_or_empty(document, "extensions"),
    )


def _decode_relation(value: JsonValue) -> MessageRelation:
    """Decode one directed relation without resolving either endpoint."""
    document = _require_object(value, "relation")
    # Endpoint resolution needs the completed document index and is therefore
    # intentionally deferred to MessageDocumentBuilder.build().
    return MessageRelation(
        source=_require_string(document.get("source"), "relation.source"),
        target=_require_string(document.get("target"), "relation.target"),
        type=OpenIdentifier(_require_string(document.get("type"), "relation.type")),
        metadata=_mapping_or_empty(document, "metadata"),
    )


def _decode_text_content(value: JsonValue) -> TextMessageContent:
    """Decode the concrete text content supported by the current fixture profile."""
    document = _require_object(value, "content")
    kind = _require_object(document.get("kind"), "content.kind")
    kind_id = _require_string(kind.get("id"), "content.kind.id")
    # The current profile contains only concrete TextMessageContent. Unknown
    # roles remain open independently and do not weaken the content scope.
    if kind_id != "content.text":
        raise AssertionError("Message Golden content must use content.text.")
    return TextMessageContent(
        id=_require_string(document.get("id"), "content.id"),
        text=_require_string(document.get("text"), "content.text"),
        metadata=_mapping_or_empty(document, "metadata"),
        extensions=_mapping_or_empty(document, "extensions"),
    )


def _decode_relations(document: dict[str, JsonValue]) -> tuple[MessageRelation, ...]:
    """Decode an optional relation array in exact declaration order."""
    if "relations" not in document:
        return ()
    values = _require_array(document["relations"], "relations")
    # Tuple construction freezes the source sequence before it enters an
    # immutable MessageEntry or MessageGroup.
    return tuple(_decode_relation(value) for value in values)


def _decode_element(value: JsonValue) -> MessageElement:
    """Reconstruct one entry or group from a schema-valid element object."""
    document = _require_object(value, "element")
    element_id = _require_string(document.get("id"), "element.id")
    kind = _decode_kind(document.get("kind"))
    child_values = _require_array(document.get("subElements"), "subElements")

    if kind.id.value == "message.entry":
        # Entry construction flows through the public Builder so fixture evidence
        # covers the same ordered accumulation and semantic validation as users.
        if child_values:
            raise AssertionError("MessageEntry subElements must remain empty.")
        builder = MessageEntryBuilder(element_id, _decode_role(document.get("role")))
        for content_value in _require_array(document.get("content"), "content"):
            builder.add_content(_decode_text_content(content_value))
        for relation in _decode_relations(document):
            builder.add_relation(relation)
        builder.with_metadata(_mapping_or_empty(document, "metadata"))
        builder.with_extensions(_mapping_or_empty(document, "extensions"))
        return builder.build()

    if kind.composition != "container":
        raise AssertionError("Valid Message Golden non-entry elements are containers.")
    # Groups recursively decode children before construction, preserving source
    # array order without introducing a parallel history representation.
    group = MessageGroup(
        id=element_id,
        kind=kind,
        sub_elements=tuple(_decode_element(child) for child in child_values),
        name=_optional_string(document.get("name"), "element.name"),
        attributes=_mapping_or_empty(document, "attributes"),
        value=document.get("value"),
        relations=_decode_relations(document),
        metadata=_mapping_or_empty(document, "metadata"),
        extensions=_mapping_or_empty(document, "extensions"),
    )
    return validate_message_group(group)


def _document_from_json(document: dict[str, JsonValue]) -> MessageDocument:
    """Reconstruct and validate one schema-valid document through public Builders."""
    root = _decode_element(document.get("root"))
    if not isinstance(root, MessageGroup):
        raise AssertionError("MessageDocument root must decode as a MessageGroup.")
    purpose = _require_string(document.get("purpose"), "purpose")
    if purpose not in ("input", "output", "context", "custom"):
        raise AssertionError("purpose must be a declared MessageDocument purpose.")

    # MessageDocumentBuilder performs complete tree validation after every child
    # Builder has produced its immutable value, including global IDs and relations.
    return (
        MessageDocumentBuilder(
            _require_string(document.get("version"), "version"),
            purpose,
            root,
        )
        .with_metadata(_mapping_or_empty(document, "metadata"))
        .with_extensions(_mapping_or_empty(document, "extensions"))
        .build()
    )


def _serialize_kind(kind: MessageElementKind) -> dict[str, JsonValue]:
    """Serialize one element Kind without normalizing its open identifier."""
    # Every independent field is emitted because composition and category cannot
    # be inferred from an otherwise equal open identifier across implementations.
    return {
        "id": kind.id.value,
        "category": kind.category,
        "composition": kind.composition,
    }


def _serialize_relation(relation: MessageRelation) -> dict[str, JsonValue]:
    """Serialize one directed relation with optional metadata."""
    document: dict[str, JsonValue] = {
        "source": relation.source,
        "target": relation.target,
        "type": relation.type.value,
    }
    # Empty metadata uses the schema default omission; non-empty values remain
    # exact and are not reordered semantically by canonical fixture comparison.
    if relation.metadata:
        document["metadata"] = dict(relation.metadata)
    return document


def _serialize_role(role: MessageRole) -> dict[str, JsonValue]:
    """Serialize standard or unknown role fields without known-value mapping."""
    document: dict[str, JsonValue] = {"id": role.id.value}
    # Optional descriptive and raw values remain independent. Unknown extensions
    # are copied without interpreting provider-specific policy keys.
    if role.semantic is not None:
        document["semantic"] = role.semantic
    if role.raw_value is not None:
        document["rawValue"] = role.raw_value
    if role.extensions:
        document["extensions"] = dict(role.extensions)
    return document


def _serialize_text_content(content: TextMessageContent) -> dict[str, JsonValue]:
    """Serialize exact text and optional JSON channels for one content item."""
    document: dict[str, JsonValue] = {
        "id": content.id,
        "kind": {"id": content.kind.id.value},
        "text": content.text,
    }
    # Text is emitted unchanged, including empty strings, newlines, emoji, and
    # Unicode normalization form; only empty default mappings are omitted.
    if content.metadata:
        document["metadata"] = dict(content.metadata)
    if content.extensions:
        document["extensions"] = dict(content.extensions)
    return document


def _serialize_element(element: MessageElement) -> dict[str, JsonValue]:
    """Serialize one immutable entry or group while preserving array order."""
    document: dict[str, JsonValue] = {
        "id": element.id,
        "kind": _serialize_kind(element.kind),
        "subElements": [_serialize_element(child) for child in element.sub_elements],
    }
    if isinstance(element, MessageEntry):
        # Entry payloads remain in content, never in subElements or generic value.
        document["role"] = _serialize_role(element.role)
        document["content"] = [
            _serialize_text_content(cast(TextMessageContent, content))
            for content in element.content
        ]
    else:
        if element.name is not None:
            document["name"] = element.name
        if element.attributes:
            document["attributes"] = dict(element.attributes)
        if element.value is not None:
            document["value"] = element.value

    # Ordered relations and non-empty JSON channels serialize identically for
    # concrete and structural element implementations.
    if element.relations:
        document["relations"] = [
            _serialize_relation(relation) for relation in element.relations
        ]
    if element.metadata:
        document["metadata"] = dict(element.metadata)
    if element.extensions:
        document["extensions"] = dict(element.extensions)
    return document


def _serialize_document(document: MessageDocument) -> dict[str, JsonValue]:
    """Serialize one validated document for canonical Golden comparison."""
    result: dict[str, JsonValue] = {
        "version": document.version,
        "purpose": document.purpose,
        "root": _serialize_element(document.root),
    }
    # Default empty mapping channels are omitted, while every preserved unknown
    # member remains available for exact canonical round-trip comparison.
    if document.metadata:
        result["metadata"] = dict(document.metadata)
    if document.extensions:
        result["extensions"] = dict(document.extensions)
    return result


def _adapter() -> SchemaValidatorAdapter:
    """Load the registered MessageDocument schema through the public adapter."""
    schema = _load_object(_SCHEMA_PATH)
    # The fixture-selected ID must match the committed schema resource before
    # any case is accepted as cross-platform conformance evidence.
    assert schema.get("$id") == _SCHEMA_ID.value
    return SchemaValidatorAdapter(SchemaLoader({_SCHEMA_ID: schema}))


def _case_document(case: JsonValue, group_name: str) -> dict[str, JsonValue]:
    """Return the input document from one named case object."""
    case_object = _require_object(case, group_name)
    _require_string(case_object.get("name"), f"{group_name}.name")
    return _require_object(case_object.get("input"), f"{group_name}.input")


def _expected_issues(case: dict[str, JsonValue]) -> tuple[SchemaValidationIssue, ...]:
    """Decode exact portable issue objects into adapter values."""
    issue_values = _require_array(case.get("expectedIssues"), "expectedIssues")
    issues: list[SchemaValidationIssue] = []
    for issue_value in issue_values:
        issue = _require_object(issue_value, "expectedIssues[]")
        # Only stable cross-language fields are admitted; platform stack traces
        # and implementation-specific codes cannot enter the Golden contract.
        if frozenset(issue) != frozenset({"path", "keyword", "message"}):
            raise AssertionError("Each expected issue must have exactly three fields.")
        issues.append(
            SchemaValidationIssue(
                path=_require_string(issue.get("path"), "issue.path"),
                keyword=_require_string(issue.get("keyword"), "issue.keyword"),
                message=_require_string(issue.get("message"), "issue.message"),
            )
        )
    return tuple(issues)


def _named_case(cases: list[JsonValue], expected_name: str) -> dict[str, JsonValue]:
    """Select exactly one case by its portable language-neutral name."""
    matches = [
        _require_object(case, "cases[]")
        for case in cases
        if isinstance(case, dict) and case.get("name") == expected_name
    ]
    # Exact uniqueness prevents a duplicate case from making assertions depend
    # on whichever same-named object a platform happens to select first.
    if len(matches) != 1:
        raise AssertionError(f"Expected exactly one case named {expected_name!r}.")
    return matches[0]


def test_message_fixture_is_registered_with_a_stable_envelope() -> None:
    """Verify discovery metadata and every portable case group are explicit."""
    index = _load_object(_INDEX_PATH)
    fixture = _load_object(_FIXTURE_PATH)
    resources = _require_array(index.get("resources"), "resources")

    # Exact envelope keys force future incompatible case-group changes through
    # explicit review rather than silent platform-specific interpretation.
    assert "message-document.json" in resources
    assert frozenset(fixture) == frozenset(
        {
            "format_version",
            "schemaId",
            "validCases",
            "invalidCases",
            "unknownRoleCases",
        }
    )
    assert fixture["format_version"] == 1
    assert fixture["schemaId"] == _SCHEMA_ID.value

    all_names: list[str] = []
    for group_name in ("validCases", "invalidCases", "unknownRoleCases"):
        for case in _require_array(fixture.get(group_name), group_name):
            case_object = _require_object(case, f"{group_name}[]")
            all_names.append(_require_string(case_object.get("name"), "case.name"))
    assert len(all_names) == len(set(all_names))


def test_message_valid_cases_match_schema_builders_and_domain_validation() -> None:
    """Verify every legal case passes portable and immutable domain boundaries."""
    fixture = _load_object(_FIXTURE_PATH)
    cases = _require_array(fixture.get("validCases"), "validCases")
    adapter = _adapter()
    assert cases

    # Schema validates the language-neutral representation first. Reconstruction
    # then exercises Entry and Document Builders plus all composed Validators.
    for case in cases:
        source = _case_document(case, "validCases[]")
        assert adapter.validate(_SCHEMA_ID, source) == ()
        document = _document_from_json(source)
        assert isinstance(document, MessageDocument)
        assert document.root.kind.id == OpenIdentifier("message.root")


def test_message_multi_turn_order_and_unicode_are_exact() -> None:
    """Verify tree/content order and Unicode code points survive reconstruction."""
    fixture = _load_object(_FIXTURE_PATH)
    cases = _require_array(fixture.get("validCases"), "validCases")
    case = _named_case(cases, "ordered-multi-turn-unicode")
    document = _document_from_json(_case_document(case, "validCases[]"))

    # Root order separates instructions, history, and current without creating a
    # second history model or flattening turns during Builder conversion.
    groups = document.root.sub_elements
    assert tuple(group.id for group in groups) == (
        "instructions",
        "history",
        "current",
    )
    instructions, history, current = groups
    assert isinstance(instructions, MessageGroup)
    assert isinstance(history, MessageGroup)
    assert isinstance(current, MessageGroup)
    assert tuple(entry.id for entry in history.sub_elements) == (
        "entry-user-1",
        "entry-assistant-1",
    )

    system_entry = instructions.sub_elements[0]
    first_user = history.sub_elements[0]
    assistant = history.sub_elements[1]
    current_user = current.sub_elements[0]
    assert isinstance(system_entry, MessageEntry)
    assert isinstance(first_user, MessageEntry)
    assert isinstance(assistant, MessageEntry)
    assert isinstance(current_user, MessageEntry)

    # Content arrays retain their own order independently from element traversal.
    # Exact comparisons cover CJK, emoji, newline, composed and decomposed forms.
    assert cast(TextMessageContent, system_entry.content[0]).text == (
        "你是一个严谨的助手。"
    )
    assert cast(TextMessageContent, first_user.content[0]).text == (
        "你好，世界 👋\n第二行"  # noqa: RUF001 - exact Golden Unicode text
    )
    assert tuple(
        cast(TextMessageContent, content).text for content in assistant.content
    ) == ("Café", "e\u0301 — preserved combining form")
    decomposed = cast(TextMessageContent, assistant.content[1]).text
    assert decomposed != unicodedata.normalize("NFC", decomposed)
    assert cast(TextMessageContent, current_user.content[0]).text == (
        "東京の天気は？ ☀️"  # noqa: RUF001 - exact Golden Unicode text
    )

    # The forward relation remains attached to its declaring Entry and resolves
    # only after the complete current group has entered the document index.
    assert assistant.relations == (
        MessageRelation(
            "entry-assistant-1",
            "entry-user-2",
            OpenIdentifier("message.precedes"),
            {"order": 1},
        ),
    )


def test_message_invalid_cases_produce_exact_schema_issues() -> None:
    """Verify every illegal case produces deterministic portable diagnostics."""
    fixture = _load_object(_FIXTURE_PATH)
    cases = _require_array(fixture.get("invalidCases"), "invalidCases")
    adapter = _adapter()
    assert cases

    # Complete tuples freeze JSON Pointer, keyword, message, and ordering rather
    # than allowing each platform to assert only an unspecified failure.
    for case_value in cases:
        case = _require_object(case_value, "invalidCases[]")
        source = _case_document(case, "invalidCases[]")
        assert adapter.validate(_SCHEMA_ID, source) == _expected_issues(case)


def test_message_unknown_role_round_trips_without_coercion() -> None:
    """Verify provider Role identity, raw text, semantics, and data remain exact."""
    fixture = _load_object(_FIXTURE_PATH)
    cases = _require_array(fixture.get("unknownRoleCases"), "unknownRoleCases")
    adapter = _adapter()
    assert cases

    for case_value in cases:
        case = _require_object(case_value, "unknownRoleCases[]")
        source = _case_document(case, "unknownRoleCases[]")
        expected = _require_object(case.get("expected"), "unknownRoleCases[].expected")
        assert adapter.validate(_SCHEMA_ID, source) == ()
        document = _document_from_json(source)

        current = document.root.sub_elements[0]
        assert isinstance(current, MessageGroup)
        entry = current.sub_elements[0]
        assert isinstance(entry, MessageEntry)
        # No known-role enum, fallback, or lowercase rewrite may replace the
        # provider identity or its exact original wire spelling.
        assert entry.role.id == OpenIdentifier("vendor.reviewer")
        assert entry.role.semantic == "Reviews the generated response."
        assert entry.role.raw_value == "Reviewer"
        assert entry.role.extensions == {"vendor.policy": "quality"}

        serialized = _serialize_document(document)
        assert json_fixtures_equal(serialized, expected)
