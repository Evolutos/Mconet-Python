"""Conformance check for the frozen R1 scope declaration."""

import json
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_EXPECTED_SCOPE: dict[str, object] = {
    "profile": "r1.text-unary",
    "reference_protocol": {
        "endpoint_path": "/v1/chat/completions",
        "id": "openai.chat-completions",
        "task": "conversation.generate",
    },
    "supported": {
        "authorization": ["none", "api-key-header", "bearer"],
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
