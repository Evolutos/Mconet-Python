"""Conformance checks for the OpenAI-compatible success response fixture."""

from __future__ import annotations

import json
from pathlib import Path

from mconet.core.domain import (
    ConversationTaskResult,
    JsonValue,
    MessageEntry,
    ModelInteractionError,
    OpenIdentifier,
    ParsedTaskResponse,
    TextMessageContent,
    validate_parsed_task_response,
)
from mconet.core.spi import ErasedRuntimeValue
from mconet.integration.openai_compatible import (
    OPENAI_CHAT_COMPLETIONS_PROTOCOL_ID,
    OpenAIChatCompletionsAdapter,
)
from mconet.testing import json_fixtures_equal

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_FIXTURE_ROOT = _PROJECT_ROOT / "spec" / "fixtures" / "r1-text-unary"
_FIXTURE_PATH = _FIXTURE_ROOT / "openai-chat-response.json"
_INDEX_PATH = _FIXTURE_ROOT / "index.json"
_JSON_VALUE = OpenIdentifier("json.value")


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


def _cases() -> list[dict[str, JsonValue]]:
    """Return every fixture case as an object."""
    fixture = _load_object(_FIXTURE_PATH)
    return [_object(case, "cases[]") for case in _array(fixture.get("cases"), "cases")]


def _parse(body: JsonValue) -> ParsedTaskResponse | BaseException:
    """Parse one decoded body; return the response or the raised exception."""
    value = ErasedRuntimeValue(_JSON_VALUE, body)
    try:
        return OpenAIChatCompletionsAdapter().parse_response(value)
    except BaseException as error:
        return error


def _project(response: ParsedTaskResponse) -> dict[str, JsonValue]:
    """Project parsed facts into the language-neutral fixture shape."""
    result = response.result
    if not isinstance(result, ConversationTaskResult):
        raise AssertionError("The result must be a ConversationTaskResult.")
    messages: list[JsonValue] = []
    for element in result.messages.root.sub_elements:
        if not isinstance(element, MessageEntry):
            raise AssertionError("Result root children must be entries.")
        # One choice has exactly one text value; joining would hide extras.
        (content,) = element.content
        if not isinstance(content, TextMessageContent):
            raise AssertionError("Result content must be text.")
        messages.append(
            {
                "extensions": dict(element.extensions),
                "id": element.id,
                "rawRole": element.role.raw_value,
                "role": element.role.id.value,
                "text": content.text,
            }
        )
    usage = response.usage
    return {
        "messages": messages,
        "resolvedModel": (
            None if response.resolved_model is None else response.resolved_model.name
        ),
        "responseExtensions": dict(response.extensions),
        "resultExtensions": dict(result.extensions),
        "status": response.status.id.value,
        "stopReason": response.stop_reason,
        "usage": (
            None
            if usage is None
            else {
                "extensions": dict(usage.extensions),
                "inputTokens": usage.input_tokens,
                "outputTokens": usage.output_tokens,
                "totalTokens": usage.total_tokens,
            }
        ),
    }


def test_response_fixture_is_registered_with_a_closed_envelope() -> None:
    """Verify discovery, envelope fields, unique names, and one outcome each."""
    index = _load_object(_INDEX_PATH)
    fixture = _load_object(_FIXTURE_PATH)

    assert "openai-chat-response.json" in _array(index.get("resources"), "resources")
    assert frozenset(fixture) == frozenset({"cases", "format_version", "protocolId"})
    assert fixture["format_version"] == 1
    assert fixture["protocolId"] == OPENAI_CHAT_COMPLETIONS_PROTOCOL_ID.value
    names = [_string(case.get("name"), "name") for case in _cases()]
    assert names
    assert len(names) == len(set(names))
    for case in _cases():
        assert ("expected" in case) != ("expectedError" in case)
        assert frozenset(case) <= frozenset(
            {"body", "expected", "expectedError", "name"}
        )


def test_every_response_case_maps_to_its_exact_facts_or_error() -> None:
    """Verify choice, usage, model, status, stop reason, and extensions."""
    for case in _cases():
        name = _string(case.get("name"), "name")
        outcome = _parse(case.get("body"))

        if "expected" in case:
            assert isinstance(outcome, ParsedTaskResponse), name
            assert validate_parsed_task_response(outcome) is outcome, name
            assert json_fixtures_equal(
                _project(outcome), _object(case["expected"], "expected")
            ), name
        else:
            expected_error = _object(case["expectedError"], "expectedError")
            assert isinstance(outcome, ModelInteractionError), name
            assert outcome.category.id.value == expected_error["category"], name
            assert outcome.phase.id.value == expected_error["phase"], name
            assert outcome.code == expected_error["code"], name


def test_response_fixture_covers_every_status_and_absent_fact() -> None:
    """Verify each finish reason branch and absent facts keep a case."""
    expected = [
        _object(case["expected"], "expected") for case in _cases() if "expected" in case
    ]
    statuses = {_string(item.get("status"), "status") for item in expected}

    assert statuses == {
        "completed",
        "incomplete",
        "filtered",
        "requires_action",
        "unknown",
    }
    assert any(item.get("usage") is None for item in expected)
    assert any(item.get("resolvedModel") is None for item in expected)
    assert any(
        _object(item.get("usage"), "usage").get("outputTokens") is None
        for item in expected
        if item.get("usage") is not None
    )
    assert len(expected) < len(_cases())
