"""Conformance checks for the OpenAI-compatible error response fixture."""

from __future__ import annotations

import json
from pathlib import Path

from mconet.core.domain import (
    HeaderField,
    Headers,
    JsonValue,
    ModelInteractionError,
    OpenIdentifier,
)
from mconet.core.spi import (
    ErasedRuntimeValue,
    TransportOutcome,
    TransportResponseMetadata,
)
from mconet.integration.openai_compatible import (
    OPENAI_CHAT_COMPLETIONS_PROTOCOL_ID,
    OpenAIChatCompletionsAdapter,
)
from mconet.testing import json_fixtures_equal

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_FIXTURE_ROOT = _PROJECT_ROOT / "spec" / "fixtures" / "r1-text-unary"
_FIXTURE_PATH = _FIXTURE_ROOT / "openai-chat-error.json"
_INDEX_PATH = _FIXTURE_ROOT / "index.json"
_JSON_VALUE = OpenIdentifier("json.value")
_SERVICE_ERROR = TransportOutcome(OpenIdentifier("service_error"))
_NANOSECONDS_PER_MILLISECOND = 1_000_000


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


def _metadata(case: dict[str, JsonValue]) -> TransportResponseMetadata:
    """Build the failed-response transport facts of one case."""
    fields: list[HeaderField] = []
    for item in _array(case.get("headers"), "headers"):
        pair = _array(item, "headers[]")
        assert len(pair) == 2
        fields.append(HeaderField(_string(pair[0], "name"), _string(pair[1], "value")))
    status = case.get("statusCode")
    request_id = case.get("requestId")
    assert status is None or type(status) is int
    assert request_id is None or isinstance(request_id, str)
    return TransportResponseMetadata(
        outcome=_SERVICE_ERROR,
        headers=Headers(tuple(fields)),
        status_code=status,
        request_id=request_id,
    )


def _project(error: ModelInteractionError) -> dict[str, JsonValue]:
    """Project one normalized error into the language-neutral fixture shape."""
    recovery = error.recovery
    assert recovery is not None
    retry_after = recovery.retry_after
    return {
        "category": error.category.id.value,
        "code": error.code,
        "message": error.message,
        "phase": error.phase.id.value,
        "recovery": {
            "requestMayHaveBeenProcessed": recovery.request_may_have_been_processed,
            "retryAfterMilliseconds": (
                None
                if retry_after is None
                else retry_after.total_nanoseconds // _NANOSECONDS_PER_MILLISECOND
            ),
            "transient": recovery.transient,
        },
        "requestId": error.request_id,
        "serviceErrorCode": error.service_error_code,
        "statusCode": error.status_code,
    }


def test_error_fixture_is_registered_with_a_closed_envelope() -> None:
    """Verify discovery, envelope fields, and unique case names."""
    index = _load_object(_INDEX_PATH)
    fixture = _load_object(_FIXTURE_PATH)

    assert "openai-chat-error.json" in _array(index.get("resources"), "resources")
    assert frozenset(fixture) == frozenset({"cases", "format_version", "protocolId"})
    assert fixture["format_version"] == 1
    assert fixture["protocolId"] == OPENAI_CHAT_COMPLETIONS_PROTOCOL_ID.value
    names = [_string(case.get("name"), "name") for case in _cases()]
    assert names
    assert len(names) == len(set(names))
    for case in _cases():
        assert frozenset(case) == frozenset(
            {"body", "expected", "headers", "name", "requestId", "statusCode"}
        )


def test_every_error_case_maps_to_its_exact_normalized_error() -> None:
    """Verify authentication, rate limit, content filter, and service errors."""
    adapter = OpenAIChatCompletionsAdapter()

    for case in _cases():
        name = _string(case.get("name"), "name")
        body = case.get("body")
        error = adapter.parse_error(
            ErasedRuntimeValue(_JSON_VALUE, body), _metadata(case)
        )
        expected = case.get("expected")

        if expected is None:
            assert error is None, name
            continue
        assert isinstance(error, ModelInteractionError), name
        assert json_fixtures_equal(_project(error), _object(expected, "expected")), name
        # Service text can echo request content or credentials, so it must
        # never reach the normalized message.
        service_message = _string(
            _object(_object(body, "body").get("error"), "error").get("message"),
            "message",
        )
        assert service_message not in error.message, name


def test_error_fixture_covers_every_normalized_branch() -> None:
    """Verify each error code and the unrecognized-body branch keep a case."""
    expected = [case.get("expected") for case in _cases()]
    codes = {
        _string(_object(item, "expected").get("code"), "code")
        for item in expected
        if item is not None
    }

    assert codes == {
        "service_authentication_failed",
        "service_permission_denied",
        "service_rate_limited",
        "service_content_filtered",
        "service_error",
    }
    assert None in expected
