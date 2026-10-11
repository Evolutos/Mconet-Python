"""Tests for the OpenAI-compatible chat message wire value."""

from collections.abc import Callable
from dataclasses import FrozenInstanceError
from types import MappingProxyType
from typing import cast

from mconet.core.domain import JsonValue, ModelInteractionError
from mconet.integration.openai_compatible import OpenAIChatMessageDTO


def _capture(action: Callable[[], object]) -> BaseException:
    """Run one action and return the exception it raises."""
    try:
        action()
    except BaseException as error:
        return error
    raise AssertionError("Expected the action to fail.")


def _protocol_error(value: JsonValue, path: str = "") -> ModelInteractionError:
    """Return the normalized failure raised while reading one message."""
    error = _capture(lambda: OpenAIChatMessageDTO.from_json(value, path))
    assert isinstance(error, ModelInteractionError)
    assert error.category.id.value == "protocol"
    assert error.phase.id.value == "response_parsing"
    assert error.code == "invalid_protocol_response"
    return error


def test_message_serializes_only_role_and_content_in_profile_order() -> None:
    """Verify request output is exactly the frozen two-member shape."""
    message = OpenAIChatMessageDTO("user", "你好 世界 👋\n第二行")

    encoded = message.to_json()

    assert encoded == {"role": "user", "content": "你好 世界 👋\n第二行"}
    assert list(encoded) == ["role", "content"]
    assert dict(message.extensions) == {}


def test_message_text_and_role_are_kept_without_normalization() -> None:
    """Verify whitespace, combining marks, and casing survive unchanged."""
    message = OpenAIChatMessageDTO("Assistant", "  e\u0301 \t")

    assert message.role == "Assistant"
    assert message.content == "  e\u0301 \t"


def test_message_reads_a_decoded_object_and_captures_unknown_members() -> None:
    """Verify unknown response members are captured but not re-sent."""
    decoded: JsonValue = {
        "role": "assistant",
        "content": "",
        "refusal": None,
        "vendor": {"trace": [1, 2]},
    }

    message = OpenAIChatMessageDTO.from_json(decoded, "/choices/0/message")

    assert message.role == "assistant"
    assert message.content == ""
    assert dict(message.extensions) == {
        "refusal": None,
        "vendor": {"trace": [1, 2]},
    }
    assert list(message.extensions) == ["refusal", "vendor"]
    assert message.to_json() == {"role": "assistant", "content": ""}


def test_message_rejects_a_non_object_with_its_location() -> None:
    """Verify the failure names the pointer and never the payload."""
    error = _protocol_error(["role", "user"], "/choices/0/message")

    assert error.message == (
        "OpenAI-compatible response field /choices/0/message must be an object."
    )


def test_message_rejects_missing_null_or_non_string_members() -> None:
    """Verify both members are required, not nullable, and textual."""
    cases: tuple[tuple[JsonValue, str], ...] = (
        ({"content": "text"}, "/m/role"),
        ({"role": None, "content": "text"}, "/m/role"),
        ({"role": "user"}, "/m/content"),
        ({"role": "user", "content": None}, "/m/content"),
        ({"role": "user", "content": ["secret-text"]}, "/m/content"),
        ({"role": 1, "content": "text"}, "/m/role"),
    )
    for decoded, location in cases:
        error = _protocol_error(decoded, "/m")
        assert error.message == (
            f"OpenAI-compatible response field {location} must be a string."
        )
        assert "secret-text" not in error.message


def test_message_root_failure_uses_the_root_pointer() -> None:
    """Verify a message read at the document root reports ``/``."""
    error = _protocol_error("text")

    assert error.message == "OpenAI-compatible response field / must be an object."


def test_message_member_names_are_escaped_in_failure_pointers() -> None:
    """Verify RFC 6901 escaping keeps member locations unambiguous."""
    error = _protocol_error({"content": "text"}, "/a~0b/c~1d")

    assert error.message.endswith("/a~0b/c~1d/role must be a string.")


def test_message_construction_requires_strings_and_portable_extensions() -> None:
    """Verify direct construction rejects values the wire cannot carry."""
    role_error = _capture(lambda: OpenAIChatMessageDTO(cast(str, None), "text"))
    content_error = _capture(lambda: OpenAIChatMessageDTO("user", cast(str, 3)))
    mapping_error = _capture(
        lambda: OpenAIChatMessageDTO("user", "text", cast(dict[str, JsonValue], []))
    )
    key_error = _capture(
        lambda: OpenAIChatMessageDTO("user", "text", cast(dict[str, JsonValue], {1: 2}))
    )
    number_error = _capture(
        lambda: OpenAIChatMessageDTO("user", "text", {"score": float("nan")})
    )

    assert isinstance(role_error, TypeError)
    assert str(role_error) == "OpenAIChatMessageDTO role must be a string."
    assert isinstance(content_error, TypeError)
    assert str(content_error) == "OpenAIChatMessageDTO content must be a string."
    assert isinstance(mapping_error, TypeError)
    assert str(mapping_error) == "OpenAIChatMessageDTO extensions must be a mapping."
    assert isinstance(key_error, TypeError)
    assert str(key_error) == "OpenAIChatMessageDTO extensions keys must be strings."
    assert isinstance(number_error, ValueError)


def test_message_is_frozen_and_detached_from_caller_extensions() -> None:
    """Verify later caller mutation cannot change a constructed message."""
    source: dict[str, JsonValue] = {"vendor": True}
    message = OpenAIChatMessageDTO("assistant", "text", source)
    source["vendor"] = False

    assert dict(message.extensions) == {"vendor": True}
    assert isinstance(
        _capture(lambda: setattr(message, "role", "user")), (FrozenInstanceError)
    )
    assert isinstance(message.extensions, MappingProxyType)
