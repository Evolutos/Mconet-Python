"""Conformance check for the frozen R1 scope declaration."""

import json
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_REFERENCE_PROTOCOL: dict[str, str] = {
    "endpoint_path": "/v1/chat/completions",
    "endpoint_profile": "compatibility/r1-openai-endpoint.json",
    "field_profile": "compatibility/r1-openai-protocol.json",
    "id": "openai.chat-completions",
    "task": "conversation.generate",
}
_RELEASE_GATES: list[dict[str, str]] = [
    {
        "condition": "Every supported behavior is implemented and every rejected behavior returns a stable pre-I/O error.",
        "id": "scope",
    },
    {
        "condition": "Every release target builds successfully.",
        "id": "build",
    },
    {
        "condition": "All domain, configuration, component, and runtime unit tests pass.",
        "id": "unit",
    },
    {
        "condition": "All replaceable component contract suites pass.",
        "id": "contract",
    },
    {
        "condition": "All r1.text-unary fixtures produce equivalent results across release platforms.",
        "id": "conformance",
    },
    {
        "condition": "All required mock-server scenarios pass.",
        "id": "integration",
    },
    {
        "condition": "At least one real OpenAI-compatible service passes controlled success and failure scenarios.",
        "id": "live",
    },
    {
        "condition": "Secret, redirect, header-injection, TLS, and response-limit checks pass.",
        "id": "security",
    },
    {
        "condition": "Client reuse, cancellation, timeout, and concurrent interaction isolation pass.",
        "id": "concurrency",
    },
    {
        "condition": "Frozen performance baselines pass without unbounded memory growth.",
        "id": "performance",
    },
    {
        "condition": "Minimal usage, custom transport, custom adapter, and error-handling documentation is executable.",
        "id": "documentation",
    },
    {
        "condition": "An isolated sample consumes only candidate release artifacts and completes a call.",
        "id": "packaging",
    },
]
_EXPECTED_SCOPE: dict[str, object] = {
    "profile": "r1.text-unary",
    "reference_protocol": _REFERENCE_PROTOCOL,
    "release_gates": _RELEASE_GATES,
    "scope_version": "r1",
    "supported": {
        "authorization": ["none", "api-key-header", "bearer"],
        "message_elements": ["message.entry"],
        "message_content": ["content.text"],
        "message_roles": ["message.system", "message.user", "message.assistant"],
        "modes": ["unary"],
        "tasks": ["conversation.generate"],
        "transports": ["http", "https"],
        "wire_formats": ["application/json"],
    },
    "unsupported": {
        "authorization": ["oauth-refresh", "body-signing", "chunked-signing"],
        "artifacts": [
            "artifact.image",
            "artifact.audio",
            "artifact.video",
            "artifact.file",
        ],
        "message_content": ["content.json", "content.artifact", "content.unknown"],
        "message_elements": ["message.tool_call", "message.tool_result"],
        "modes": ["server_stream", "client_stream", "duplex", "long_running"],
        "tasks": [
            "embedding.create",
            "rerank.documents",
            "image.generate",
            "audio.transcribe",
            "video.generate",
        ],
        "transports": ["websocket", "grpc", "quic"],
        "wire_formats": ["protobuf", "xml", "custom-binary"],
    },
}


def test_r1_scope_matches_frozen_profile() -> None:
    # Compare the complete profile so unsupported capabilities cannot drift silently.
    actual: object = json.loads(
        (_PROJECT_ROOT / "spec" / "r1-scope.json").read_text(encoding="utf-8")
    )
    assert actual == _EXPECTED_SCOPE


def test_r1_scope_protocol_profiles_exist() -> None:
    """Verify every reference protocol document is present in the spec module."""
    # Scope links are release-review inputs, so broken or external paths must
    # fail conformance before a candidate can reach packaging.
    for key in ("endpoint_profile", "field_profile"):
        relative = _REFERENCE_PROTOCOL[key]
        path = _PROJECT_ROOT / "spec" / relative
        assert path.is_file()


def test_r1_scope_release_gate_ids_are_complete_and_unique() -> None:
    """Verify the release review contains every architecture gate exactly once."""
    # Ordered IDs provide a compact audit checklist while full conditions remain
    # in the frozen Scope document.
    identifiers = [gate["id"] for gate in _RELEASE_GATES]
    assert identifiers == [
        "scope",
        "build",
        "unit",
        "contract",
        "conformance",
        "integration",
        "live",
        "security",
        "concurrency",
        "performance",
        "documentation",
        "packaging",
    ]
    assert len(identifiers) == len(set(identifiers))
