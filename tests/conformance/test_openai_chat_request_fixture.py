"""Conformance checks for the OpenAI-compatible protocol request fixture."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, cast

from mconet.core.domain import (
    CompatibilityPolicy,
    ConversationInputNode,
    ConversationTaskBuilder,
    Extensions,
    GenerationParameters,
    GenerationParametersNode,
    HeaderField,
    Headers,
    JsonValue,
    MessageDocument,
    MessageElement,
    MessageEntry,
    MessageGroup,
    ModelDescriptor,
    ModelInteractionError,
    ModelRequest,
    ModelRequestBuilder,
    NamedModel,
    OpenIdentifier,
    QueryParameters,
    ResolvedServiceAccess,
    TaskDocument,
    TaskGroupNode,
    TaskNode,
    TextMessageContent,
    UriValue,
)
from mconet.integration.openai_compatible import (
    OPENAI_CHAT_COMPLETIONS_PROTOCOL_ID,
    OpenAIChatCompletionsAdapter,
)
from mconet.testing import json_fixtures_equal

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_FIXTURE_ROOT = _PROJECT_ROOT / "spec" / "fixtures" / "r1-text-unary"
_FIXTURE_PATH = _FIXTURE_ROOT / "openai-chat-request.json"
_INDEX_PATH = _FIXTURE_ROOT / "index.json"
_PARAMETER_NAMES = frozenset({"maxOutputTokens", "seed", "stop", "temperature", "topP"})


def _empty_extensions() -> Extensions:
    """Create independent empty extension storage."""
    return {}


@dataclass(frozen=True, slots=True)
class _Kind:
    """Message element kind decoded from the compact fixture shape."""

    id: OpenIdentifier
    category: str
    composition: Literal["leaf", "container"]


@dataclass(frozen=True, slots=True)
class _Role:
    """Open message role decoded from a fixture entry."""

    id: OpenIdentifier
    semantic: str | None = None
    raw_value: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _TaskKind:
    """Task node kind for the fixture task root."""

    id: OpenIdentifier
    composition: Literal["leaf", "container"] = "container"


@dataclass(frozen=True, slots=True)
class _Target:
    """Model target for the protocol under test."""

    service_id: OpenIdentifier
    protocol_id: OpenIdentifier
    model: ModelDescriptor
    deployment_id: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _Mode:
    """Unary interaction mode."""

    id: OpenIdentifier = field(default_factory=lambda: OpenIdentifier("unary"))


@dataclass(frozen=True, slots=True)
class _Authorization:
    """Opaque authorization carried into the plan."""

    kind: OpenIdentifier = field(
        default_factory=lambda: OpenIdentifier("authorization.none")
    )


def _load_object(path: Path) -> dict[str, JsonValue]:
    """Load one committed UTF-8 JSON document with an object root."""
    document: JsonValue = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise AssertionError(f"Expected a JSON object in {path}.")
    return document


def _object(value: JsonValue | None, name: str) -> dict[str, JsonValue]:
    """Return one required object field."""
    if not isinstance(value, dict):
        raise AssertionError(f"{name} must be a JSON object.")
    return value


def _array(value: JsonValue | None, name: str) -> list[JsonValue]:
    """Return one required array field in source order."""
    if not isinstance(value, list):
        raise AssertionError(f"{name} must be a JSON array.")
    return value


def _string(value: JsonValue | None, name: str) -> str:
    """Return one required string field without coercion."""
    if not isinstance(value, str):
        raise AssertionError(f"{name} must be a JSON string.")
    return value


def _element(value: JsonValue, path: str) -> MessageElement:
    """Decode one compact entry or group in source order."""
    document = _object(value, path)
    if "group" in document:
        children = _array(document.get("children"), f"{path}.children")
        return MessageGroup(
            _string(document["group"], f"{path}.group"),
            _Kind(OpenIdentifier("message.group"), "group", "container"),
            tuple(
                _element(child, f"{path}.children[{index}]")
                for index, child in enumerate(children)
            ),
        )
    raw_value = document.get("rawValue")
    if raw_value is not None and not isinstance(raw_value, str):
        raise AssertionError(f"{path}.rawValue must be a string.")
    texts = _array(document.get("texts"), f"{path}.texts")
    entry_id = f"{path.replace('[', '-').replace(']', '').replace('.', '-')}"
    return MessageEntry(
        entry_id,
        _Role(
            OpenIdentifier(_string(document.get("role"), f"{path}.role")),
            None,
            raw_value,
        ),
        tuple(
            TextMessageContent(f"{entry_id}-text-{index}", _string(text, "text"))
            for index, text in enumerate(texts)
        ),
    )


def _parameters(document: dict[str, JsonValue]) -> GenerationParameters:
    """Decode the compact generation parameters of one case."""
    unknown = frozenset(document) - _PARAMETER_NAMES
    if unknown:
        raise AssertionError(f"Unknown parameter fields: {sorted(unknown)}.")
    stop = document.get("stop", [])
    return GenerationParameters(
        temperature=cast(float | None, document.get("temperature")),
        top_p=cast(float | None, document.get("topP")),
        max_output_tokens=cast(int | None, document.get("maxOutputTokens")),
        stop=tuple(_string(item, "stop[]") for item in _array(stop, "stop")),
        seed=cast(int | None, document.get("seed")),
    )


def _request(case: dict[str, JsonValue], model: str) -> ModelRequest:
    """Build the validated conversation request of one case."""
    entries = _array(case.get("entries"), "entries")
    root = MessageGroup(
        "root",
        _Kind(OpenIdentifier("message.root"), "root", "container"),
        tuple(
            _element(entry, f"entries[{index}]") for index, entry in enumerate(entries)
        ),
    )
    children: tuple[TaskNode, ...] = (
        ConversationInputNode("input", MessageDocument("1.0", "input", root)),
    )
    if "parameters" in case:
        parameters = _parameters(_object(case["parameters"], "parameters"))
        children = (*children, GenerationParametersNode("parameters", parameters))
    document = TaskDocument(
        "1.0", TaskGroupNode("root", _TaskKind(OpenIdentifier("task.root")), children)
    )
    target = _Target(
        OpenIdentifier("service.vendor"),
        OPENAI_CHAT_COMPLETIONS_PROTOCOL_ID,
        NamedModel(model),
    )
    return ModelRequestBuilder(
        target, ConversationTaskBuilder(document).build()
    ).build()


def _access() -> ResolvedServiceAccess:
    """Return resolved access for an allowed endpoint."""
    return ResolvedServiceAccess(
        endpoint=UriValue("https://models.example.test", True),
        authorization=_Authorization(),
        headers=Headers((HeaderField("X-Trace", "fixture"),)),
        query=QueryParameters(),
        api_version=None,
        project_id=None,
        tenant_id=None,
        extensions={},
    )


def _build_body(
    adapter: OpenAIChatCompletionsAdapter, request: ModelRequest
) -> dict[str, JsonValue] | BaseException:
    """Plan and build one request; return its body or the raised exception."""
    plan = adapter.prepare_plan(request, _access(), _Mode())
    try:
        request_plan = adapter.build_request(request, plan)
    except BaseException as error:
        return error
    assert request_plan.execution_plan is plan
    return cast(dict[str, JsonValue], request_plan.payload.value_as(dict))


def _cases() -> list[dict[str, JsonValue]]:
    """Return every fixture case as an object."""
    fixture = _load_object(_FIXTURE_PATH)
    return [_object(case, "cases[]") for case in _array(fixture.get("cases"), "cases")]


def test_request_fixture_is_registered_with_a_closed_envelope() -> None:
    """Verify discovery, envelope fields, and unique case names."""
    index = _load_object(_INDEX_PATH)
    fixture = _load_object(_FIXTURE_PATH)

    assert "openai-chat-request.json" in _array(index.get("resources"), "resources")
    assert frozenset(fixture) == frozenset(
        {"cases", "format_version", "model", "protocolId"}
    )
    assert fixture["format_version"] == 1
    assert fixture["protocolId"] == OPENAI_CHAT_COMPLETIONS_PROTOCOL_ID.value
    names = [_string(case.get("name"), "name") for case in _cases()]
    assert names
    assert len(names) == len(set(names))
    for case in _cases():
        # Exactly one outcome keeps every case an unambiguous assertion.
        assert ("expectedBody" in case) != ("expectedError" in case)
        assert frozenset(case) <= frozenset(
            {"entries", "expectedBody", "expectedError", "name", "parameters", "policy"}
        )


def test_every_request_case_maps_to_its_exact_wire_body_or_error() -> None:
    """Verify message mapping, each parameter, and policy outcomes are stable."""
    fixture = _load_object(_FIXTURE_PATH)
    model = _string(fixture.get("model"), "model")

    for case in _cases():
        name = _string(case.get("name"), "name")
        policy = CompatibilityPolicy(
            OpenIdentifier(_string(case.get("policy"), "policy"))
        )
        outcome = _build_body(
            OpenAIChatCompletionsAdapter(policy), _request(case, model)
        )

        if "expectedBody" in case:
            assert not isinstance(outcome, BaseException), name
            expected = _object(case["expectedBody"], "expectedBody")
            body = outcome
            assert json_fixtures_equal(body, expected), name
            # The profile fixes member order, so it is compared separately from
            # the order-insensitive JSON value equality.
            assert list(body) == list(expected), name
        else:
            expected_error = _object(case["expectedError"], "expectedError")
            error = outcome
            assert isinstance(error, ModelInteractionError), name
            assert error.category.id.value == expected_error["category"], name
            assert error.phase.id.value == expected_error["phase"], name
            assert error.code == expected_error["code"], name


def test_request_fixture_covers_every_parameter_and_policy_branch() -> None:
    """Verify the fixture keeps a case for each mapped member and outcome."""
    bodies = [
        _object(case["expectedBody"], "expectedBody")
        for case in _cases()
        if "expectedBody" in case
    ]
    sent_members = {member for body in bodies for member in body}
    error_codes = {
        _string(_object(case["expectedError"], "expectedError").get("code"), "code")
        for case in _cases()
        if "expectedError" in case
    }
    policies = {_string(case.get("policy"), "policy") for case in _cases()}

    assert sent_members == {
        "model",
        "messages",
        "temperature",
        "top_p",
        "max_tokens",
        "stop",
        "seed",
        "stream",
    }
    assert error_codes == {
        "unsupported_generation_parameter",
        "unsupported_message_role",
        "empty_conversation",
    }
    assert policies == {"strict", "compatible"}
