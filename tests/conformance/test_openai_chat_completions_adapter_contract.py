"""Shared adapter contract run against the OpenAI-compatible adapter."""

from __future__ import annotations

import json
from collections.abc import Callable
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
    MediaType,
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
    ParsedTaskResponse,
    QueryParameters,
    ResolvedServiceAccess,
    TaskDocument,
    TaskGroupNode,
    TaskNode,
    TextMessageContent,
    UriValue,
    validate_parsed_task_response,
)
from mconet.core.spi import (
    ErasedRuntimeValue,
    ProtocolExecutionPlan,
    ProtocolRequestPlan,
    TransportOutcome,
    TransportResponseMetadata,
)
from mconet.integration.openai_compatible import (
    OPENAI_CHAT_COMPLETIONS_PROTOCOL_ID,
    OpenAIChatCompletionsAdapter,
)
from mconet.testing import AdapterContractSuite, json_fixtures_equal

_FIXTURE_ROOT = (
    Path(__file__).resolve().parents[2] / "spec" / "fixtures" / "r1-text-unary"
)
_JSON_VALUE = OpenIdentifier("json.value")
_JSON = MediaType("application", "json")
_SERVICE_ERROR = TransportOutcome(OpenIdentifier("service_error"))
_ENDPOINT = UriValue("https://models.example.test", True)


def _empty_extensions() -> Extensions:
    """Create independent empty extension storage."""
    return {}


@dataclass(frozen=True, slots=True)
class _Kind:
    """Message element kind for compact fixture entries and groups."""

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
    """Complete structural model target."""

    service_id: OpenIdentifier
    protocol_id: OpenIdentifier
    model: ModelDescriptor
    deployment_id: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _Task:
    """Complete structural task descriptor."""

    type: OpenIdentifier
    version: str | None = None
    input_schema_id: str | None = None
    output_schema_id: str | None = None
    metadata: Extensions = field(default_factory=_empty_extensions)
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _Mode:
    """Structural interaction mode."""

    id: OpenIdentifier


@dataclass(frozen=True, slots=True)
class _Authorization:
    """Opaque authorization carried into the plan."""

    kind: OpenIdentifier = field(
        default_factory=lambda: OpenIdentifier("authorization.none")
    )


_UNARY = _Mode(OpenIdentifier("unary"))
_CONVERSATION = _Task(OpenIdentifier("conversation.generate"))


def _load(name: str) -> dict[str, JsonValue]:
    """Load one committed fixture resource with an object root."""
    document: JsonValue = json.loads((_FIXTURE_ROOT / name).read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise AssertionError(f"Expected a JSON object in {name}.")
    return document


def _cases(name: str) -> list[dict[str, JsonValue]]:
    """Return every case object of one fixture resource."""
    cases = _load(name).get("cases")
    assert isinstance(cases, list)
    return [cast(dict[str, JsonValue], case) for case in cases]


def _capture(action: Callable[[], object]) -> BaseException:
    """Run one action and return the exception it raises."""
    try:
        action()
    except BaseException as error:
        return error
    raise AssertionError("Expected the action to fail.")


def _element(value: JsonValue, path: str) -> MessageElement:
    """Decode one compact request fixture entry or group."""
    document = cast(dict[str, JsonValue], value)
    if "group" in document:
        children = cast(list[JsonValue], document["children"])
        return MessageGroup(
            cast(str, document["group"]),
            _Kind(OpenIdentifier("message.group"), "group", "container"),
            tuple(
                _element(child, f"{path}-{index}")
                for index, child in enumerate(children)
            ),
        )
    texts = cast(list[str], document["texts"])
    return MessageEntry(
        path,
        _Role(
            OpenIdentifier(cast(str, document["role"])),
            raw_value=cast(str | None, document.get("rawValue")),
        ),
        tuple(
            TextMessageContent(f"{path}-text-{index}", text)
            for index, text in enumerate(texts)
        ),
    )


def _request(case: dict[str, JsonValue], model: str) -> ModelRequest:
    """Build the validated conversation request of one request fixture case."""
    entries = cast(list[JsonValue], case["entries"])
    root = MessageGroup(
        "root",
        _Kind(OpenIdentifier("message.root"), "root", "container"),
        tuple(_element(entry, f"entry-{index}") for index, entry in enumerate(entries)),
    )
    children: tuple[TaskNode, ...] = (
        ConversationInputNode("input", MessageDocument("1.0", "input", root)),
    )
    if "parameters" in case:
        values = cast(dict[str, JsonValue], case["parameters"])
        parameters = GenerationParameters(
            temperature=cast(float | None, values.get("temperature")),
            top_p=cast(float | None, values.get("topP")),
            max_output_tokens=cast(int | None, values.get("maxOutputTokens")),
            stop=tuple(cast(list[str], values.get("stop", []))),
            seed=cast(int | None, values.get("seed")),
        )
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
        endpoint=_ENDPOINT,
        authorization=_Authorization(),
        headers=Headers((HeaderField("X-Trace", "contract"),)),
        query=QueryParameters(),
        api_version=None,
        project_id=None,
        tenant_id=None,
        extensions={},
    )


def _suite(policy: str = "compatible") -> AdapterContractSuite:
    """Return the shared contract suite for one adapter policy."""
    return AdapterContractSuite(
        OpenAIChatCompletionsAdapter(CompatibilityPolicy(OpenIdentifier(policy)))
    )


def test_supports_contract_accepts_only_the_frozen_combination() -> None:
    """Verify exact protocol, task type, and mode applicability."""
    suite = _suite()
    protocol = OPENAI_CHAT_COMPLETIONS_PROTOCOL_ID
    for service in ("service.openai", "service.local"):
        target = _Target(OpenIdentifier(service), protocol, NamedModel("any"))
        suite.assert_supports(target, _CONVERSATION, _UNARY, expected=True)

    target = _Target(OpenIdentifier("service.openai"), protocol, NamedModel("any"))
    other_protocol = _Target(
        OpenIdentifier("service.openai"),
        OpenIdentifier("openai.responses"),
        NamedModel("any"),
    )
    suite.assert_supports(other_protocol, _CONVERSATION, _UNARY, expected=False)
    suite.assert_supports(
        target, _Task(OpenIdentifier("embedding.create")), _UNARY, expected=False
    )
    suite.assert_supports(
        target, _CONVERSATION, _Mode(OpenIdentifier("server_stream")), expected=False
    )


def test_plan_and_build_contract_hold_for_every_request_fixture_case() -> None:
    """Verify planning and request building for each success and failure case."""
    model = cast(str, _load("openai-chat-request.json")["model"])

    for case in _cases("openai-chat-request.json"):
        name = cast(str, case["name"])
        suite = _suite(cast(str, case["policy"]))
        request = _request(case, model)
        plans: list[ProtocolExecutionPlan] = []

        def check_plan(
            plan: ProtocolExecutionPlan, plans: list[ProtocolExecutionPlan] = plans
        ) -> None:
            assert plan.transport_plan.endpoint == _ENDPOINT
            assert plan.transport_plan.method == "POST"
            assert plan.payload_encoder.media_type == _JSON
            assert plan.success_decoder.media_type == _JSON
            assert plan.error_decoder.media_type == _JSON
            plans.append(plan)

        suite.assert_prepare_plan(request, _access(), _UNARY, assertion=check_plan)
        expected_body = case.get("expectedBody")

        def check_request(
            request_plan: ProtocolRequestPlan, expected: JsonValue = expected_body
        ) -> None:
            assert request_plan.payload.type_id == _JSON_VALUE
            assert json_fixtures_equal(
                cast(JsonValue, request_plan.payload.value), expected
            )

        if expected_body is not None:
            suite.assert_build_request(request, plans[0], assertion=check_request)
            continue
        # Failures pass through the suite unchanged as normalized errors.
        error = _capture(
            lambda suite=suite, request=request, plan=plans[0]: (
                suite.assert_build_request(request, plan, assertion=check_request)
            )
        )
        assert isinstance(error, ModelInteractionError), name
        expected_error = cast(dict[str, JsonValue], case["expectedError"])
        assert error.code == expected_error["code"], name


def test_parse_response_contract_holds_for_every_response_fixture_case() -> None:
    """Verify success parsing for each case and pass-through of violations."""
    suite = _suite()

    for case in _cases("openai-chat-response.json"):
        name = cast(str, case["name"])
        response = ErasedRuntimeValue(_JSON_VALUE, case["body"])
        expected = case.get("expected")

        def check(parsed: ParsedTaskResponse, expected: JsonValue = expected) -> None:
            assert validate_parsed_task_response(parsed) is parsed
            facts = cast(dict[str, JsonValue], expected)
            assert parsed.status.id.value == facts["status"]
            assert parsed.stop_reason == facts["stopReason"]

        if expected is not None:
            suite.assert_parse_response(response, assertion=check)
            continue
        error = _capture(
            lambda response=response: suite.assert_parse_response(
                response, assertion=check
            )
        )
        assert isinstance(error, ModelInteractionError), name
        assert error.code == "invalid_protocol_response", name


def test_parse_error_contract_holds_for_every_error_fixture_case() -> None:
    """Verify each mapped error and each unrecognized body through the suite."""
    suite = _suite()

    for case in _cases("openai-chat-error.json"):
        headers = Headers(
            tuple(
                HeaderField(cast(str, pair[0]), cast(str, pair[1]))
                for pair in cast(list[list[JsonValue]], case["headers"])
            )
        )
        metadata = TransportResponseMetadata(
            outcome=_SERVICE_ERROR,
            headers=headers,
            status_code=cast(int | None, case["statusCode"]),
            request_id=cast(str | None, case["requestId"]),
        )
        expected = case.get("expected")

        def check(
            error: ModelInteractionError | None, expected: JsonValue = expected
        ) -> None:
            if expected is None:
                assert error is None
                return
            assert error is not None
            facts = cast(dict[str, JsonValue], expected)
            assert error.category.id.value == facts["category"]
            assert error.code == facts["code"]
            assert error.status_code == facts["statusCode"]

        suite.assert_parse_error(
            ErasedRuntimeValue(_JSON_VALUE, case["body"]), metadata, assertion=check
        )
