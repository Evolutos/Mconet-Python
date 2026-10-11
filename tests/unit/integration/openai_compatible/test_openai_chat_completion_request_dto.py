"""Tests for the OpenAI-compatible chat completion request wire value."""

from collections.abc import Callable
from dataclasses import FrozenInstanceError
from typing import cast

from mconet.integration.openai_compatible._openai_chat_completion_request_dto import (
    OpenAIChatCompletionRequestDTO,
)
from mconet.integration.openai_compatible._openai_chat_message_dto import (
    OpenAIChatMessageDTO,
)

_MESSAGES = (
    OpenAIChatMessageDTO("system", "Be exact."),
    OpenAIChatMessageDTO("user", "Hello"),
)


def _capture(action: Callable[[], object]) -> BaseException:
    """Run one action and return the exception it raises."""
    try:
        action()
    except BaseException as error:
        return error
    raise AssertionError("Expected the action to fail.")


def test_request_with_only_required_members_sends_stream_false() -> None:
    """Verify omitted options are absent and unary streaming is explicit."""
    request = OpenAIChatCompletionRequestDTO("model-a", _MESSAGES)

    encoded = request.to_json()

    assert encoded == {
        "model": "model-a",
        "messages": [
            {"role": "system", "content": "Be exact."},
            {"role": "user", "content": "Hello"},
        ],
        "stream": False,
    }
    assert request.stream is False


def test_request_writes_every_member_in_frozen_profile_order() -> None:
    """Verify member order matches the frozen request field profile."""
    request = OpenAIChatCompletionRequestDTO(
        "model-a",
        _MESSAGES,
        temperature=0.25,
        top_p=1,
        max_tokens=512,
        stop=("<END>", "停止"),
        seed=0,
    )

    encoded = request.to_json()

    assert list(encoded) == [
        "model",
        "messages",
        "temperature",
        "top_p",
        "max_tokens",
        "stop",
        "seed",
        "stream",
    ]
    assert encoded["temperature"] == 0.25
    assert encoded["top_p"] == 1
    assert encoded["max_tokens"] == 512
    assert encoded["stop"] == ["<END>", "停止"]
    assert encoded["seed"] == 0


def test_request_zero_values_are_sent_rather_than_omitted() -> None:
    """Verify only None omits a member; zero is an explicit value."""
    encoded = OpenAIChatCompletionRequestDTO(
        "model-a", _MESSAGES, temperature=0.0, top_p=0.0, max_tokens=0, seed=0
    ).to_json()

    assert encoded["temperature"] == 0.0
    assert encoded["top_p"] == 0.0
    assert encoded["max_tokens"] == 0
    assert encoded["seed"] == 0


def test_request_json_is_a_fresh_object_on_each_call() -> None:
    """Verify callers cannot change the request through returned JSON."""
    request = OpenAIChatCompletionRequestDTO("model-a", _MESSAGES, stop=("x",))

    first = request.to_json()
    first["model"] = "changed"
    second = request.to_json()

    assert second["model"] == "model-a"
    assert second["stop"] == ["x"]


def test_request_requires_a_model_and_a_non_empty_message_tuple() -> None:
    """Verify required members are present with their wire types."""
    model_error = _capture(
        lambda: OpenAIChatCompletionRequestDTO(cast(str, None), _MESSAGES)
    )
    list_error = _capture(
        lambda: OpenAIChatCompletionRequestDTO(
            "model-a", cast(tuple[OpenAIChatMessageDTO, ...], list(_MESSAGES))
        )
    )
    empty_error = _capture(lambda: OpenAIChatCompletionRequestDTO("model-a", ()))
    member_error = _capture(
        lambda: OpenAIChatCompletionRequestDTO(
            "model-a",
            cast(tuple[OpenAIChatMessageDTO, ...], ({"role": "user"},)),
        )
    )

    assert isinstance(model_error, TypeError)
    assert str(model_error) == "OpenAIChatCompletionRequestDTO model must be a string."
    assert isinstance(list_error, TypeError)
    assert isinstance(empty_error, ValueError)
    assert str(empty_error) == (
        "OpenAIChatCompletionRequestDTO messages must not be empty."
    )
    assert isinstance(member_error, TypeError)


def test_request_rejects_booleans_and_wrong_numeric_kinds() -> None:
    """Verify bool never passes as a JSON number."""
    temperature_error = _capture(
        lambda: OpenAIChatCompletionRequestDTO(
            "model-a", _MESSAGES, temperature=cast(float, True)
        )
    )
    top_p_error = _capture(
        lambda: OpenAIChatCompletionRequestDTO(
            "model-a", _MESSAGES, top_p=cast(float, "0.9")
        )
    )
    max_tokens_error = _capture(
        lambda: OpenAIChatCompletionRequestDTO(
            "model-a", _MESSAGES, max_tokens=cast(int, 1.0)
        )
    )
    seed_error = _capture(
        lambda: OpenAIChatCompletionRequestDTO(
            "model-a", _MESSAGES, seed=cast(int, False)
        )
    )

    assert isinstance(temperature_error, TypeError)
    assert str(temperature_error) == (
        "OpenAIChatCompletionRequestDTO temperature must be a number or None."
    )
    assert isinstance(top_p_error, TypeError)
    assert isinstance(max_tokens_error, TypeError)
    assert str(max_tokens_error) == (
        "OpenAIChatCompletionRequestDTO max_tokens must be an integer or None."
    )
    assert isinstance(seed_error, TypeError)


def test_request_rejects_numbers_without_a_portable_json_encoding() -> None:
    """Verify non-finite floats and unsafe integers fail before encoding."""
    actions: tuple[Callable[[], object], ...] = (
        lambda: OpenAIChatCompletionRequestDTO(
            "model-a", _MESSAGES, temperature=float("inf")
        ),
        lambda: OpenAIChatCompletionRequestDTO(
            "model-a", _MESSAGES, top_p=float("nan")
        ),
        lambda: OpenAIChatCompletionRequestDTO("model-a", _MESSAGES, max_tokens=2**53),
        lambda: OpenAIChatCompletionRequestDTO("model-a", _MESSAGES, seed=-(2**53)),
    )
    for action in actions:
        assert isinstance(_capture(action), ValueError)


def test_request_stop_is_a_non_empty_string_tuple_or_none() -> None:
    """Verify stop cannot send an empty array or a non-string sequence."""
    empty_error = _capture(
        lambda: OpenAIChatCompletionRequestDTO("model-a", _MESSAGES, stop=())
    )
    list_error = _capture(
        lambda: OpenAIChatCompletionRequestDTO(
            "model-a", _MESSAGES, stop=cast(tuple[str, ...], ["x"])
        )
    )
    member_error = _capture(
        lambda: OpenAIChatCompletionRequestDTO(
            "model-a", _MESSAGES, stop=cast(tuple[str, ...], ("x", 1))
        )
    )

    assert isinstance(empty_error, ValueError)
    assert str(empty_error) == (
        "OpenAIChatCompletionRequestDTO stop must not be empty; use None to omit it."
    )
    assert isinstance(list_error, TypeError)
    assert isinstance(member_error, TypeError)
    assert str(member_error) == (
        "OpenAIChatCompletionRequestDTO stop must contain only strings."
    )


def test_request_is_frozen() -> None:
    """Verify a built request cannot be changed before encoding."""
    request = OpenAIChatCompletionRequestDTO("model-a", _MESSAGES)

    error = _capture(lambda: setattr(request, "model", "model-b"))

    assert isinstance(error, FrozenInstanceError)
