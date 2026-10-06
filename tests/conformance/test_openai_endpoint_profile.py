"""Conformance contract for the OpenAI-compatible endpoint shape."""

import json
from pathlib import Path
from typing import cast

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_ENDPOINT_PATH = _PROJECT_ROOT / "spec" / "compatibility" / "r1-openai-endpoint.json"
_SCOPE_PATH = _PROJECT_ROOT / "spec" / "r1-scope.json"
_EXPECTED_ENDPOINT: dict[str, object] = {
    "base_url": {
        "fragment": "forbidden",
        "query": "forbidden",
        "source": "service-access",
    },
    "format_version": 1,
    "method": "POST",
    "path": "/v1/chat/completions",
    "profile": "r1.text-unary",
    "protocol": "openai.chat-completions",
    "version": {
        "location": "path",
        "value": "v1",
    },
}


def _load_json_object(path: Path) -> dict[str, object]:
    """Load a conformance document and require an object at its root."""
    document: object = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return _as_string_mapping(cast(object, document))


def _as_string_mapping(value: object) -> dict[str, object]:
    """Narrow an untyped JSON object to a string-keyed mapping."""
    assert isinstance(value, dict)
    mapping: dict[str, object] = {}
    for key, item in cast(dict[object, object], value).items():
        assert isinstance(key, str)
        mapping[key] = item
    return mapping


def test_openai_endpoint_matches_frozen_profile() -> None:
    """Require the reviewed method, path, version, and base URL rules."""
    # Compare the entire profile so version placement or URL composition cannot
    # drift as an incidental integration change.
    assert _load_json_object(_ENDPOINT_PATH) == _EXPECTED_ENDPOINT


def test_openai_endpoint_matches_r1_scope() -> None:
    """Require the endpoint profile and reference protocol to agree."""
    # The scope is the release-facing capability declaration; this cross-check
    # prevents it from naming a different protocol or endpoint path.
    endpoint = _load_json_object(_ENDPOINT_PATH)
    scope = _load_json_object(_SCOPE_PATH)
    reference_protocol = _as_string_mapping(scope.get("reference_protocol"))
    assert reference_protocol.get("id") == endpoint["protocol"]
    assert reference_protocol.get("endpoint_path") == endpoint["path"]
    assert scope.get("profile") == endpoint["profile"]
