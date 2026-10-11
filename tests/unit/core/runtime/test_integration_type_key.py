"""Tests for the exact model integration type table key."""

from collections.abc import Callable
from dataclasses import FrozenInstanceError, dataclass, fields
from typing import cast

from mconet.core.domain import (
    InteractionMode,
    ModelTarget,
    OpenIdentifier,
    TaskDescriptor,
)
from mconet.core.runtime._integration_type_key import IntegrationTypeKey

_PROTOCOL = OpenIdentifier("openai.chat-completions")
_TASK = OpenIdentifier("conversation.generate")
_MODE = OpenIdentifier("unary")


def _capture(action: Callable[[], object]) -> BaseException:
    """Run one action and return the exception it raises."""
    try:
        action()
    except BaseException as error:
        return error
    raise AssertionError("Expected the action to fail.")


@dataclass(frozen=True, slots=True)
class _Target:
    """Target exposing only the protocol a key may read."""

    protocol_id: OpenIdentifier


@dataclass(frozen=True, slots=True)
class _Task:
    """Task descriptor exposing only the type a key may read."""

    type: OpenIdentifier


@dataclass(frozen=True, slots=True)
class _Mode:
    """Interaction mode exposing only its identifier."""

    id: OpenIdentifier


def test_key_keeps_protocol_task_and_mode_as_separate_fields() -> None:
    """Verify the key has exactly three parts and no model name."""
    key = IntegrationTypeKey(_PROTOCOL, _TASK, _MODE)

    assert [item.name for item in fields(IntegrationTypeKey)] == [
        "protocol_id",
        "task_type",
        "mode_id",
    ]
    assert (key.protocol_id, key.task_type, key.mode_id) == (_PROTOCOL, _TASK, _MODE)


def test_key_is_an_immutable_hashable_value() -> None:
    """Verify equal parts give equal keys usable in a mapping."""
    first = IntegrationTypeKey(_PROTOCOL, _TASK, _MODE)
    second = IntegrationTypeKey(
        OpenIdentifier("openai.chat-completions"),
        OpenIdentifier("conversation.generate"),
        OpenIdentifier("unary"),
    )

    assert first == second
    assert {first: 1}[second] == 1
    error = _capture(lambda: setattr(first, "mode_id", OpenIdentifier("duplex")))
    assert isinstance(error, FrozenInstanceError)


def test_key_requires_valid_open_identifiers() -> None:
    """Verify each part is a nominal identifier with the shared grammar."""
    for index in range(3):
        parts: list[object] = [_PROTOCOL, _TASK, _MODE]
        parts[index] = "unary"
        error = _capture(
            lambda parts=parts: IntegrationTypeKey(
                *cast(tuple[OpenIdentifier, OpenIdentifier, OpenIdentifier], parts)
            )
        )

        assert isinstance(error, TypeError)

    for text in ("a/b", "Unary", "", "a b"):
        error = _capture(
            lambda text=text: IntegrationTypeKey(_PROTOCOL, _TASK, OpenIdentifier(text))
        )

        assert isinstance(error, ValueError)


def test_key_for_request_reads_protocol_task_type_and_mode_only() -> None:
    """Verify request values map to the key without any other target field."""
    # The fixtures are partial on purpose: reading any other field would fail.
    key = IntegrationTypeKey.for_request(
        cast(ModelTarget, _Target(_PROTOCOL)),
        cast(TaskDescriptor, _Task(_TASK)),
        cast(InteractionMode, _Mode(_MODE)),
    )

    assert key == IntegrationTypeKey(_PROTOCOL, _TASK, _MODE)


def test_serialization_is_the_canonical_cross_language_text() -> None:
    """Verify the fixed text form that every SDK must reproduce."""
    cases = (
        (
            IntegrationTypeKey(_PROTOCOL, _TASK, _MODE),
            "openai.chat-completions/conversation.generate/unary",
        ),
        (
            IntegrationTypeKey(
                OpenIdentifier("vendor.rpc_v2"),
                OpenIdentifier("embedding.create"),
                OpenIdentifier("server_stream"),
            ),
            "vendor.rpc_v2/embedding.create/server_stream",
        ),
    )
    for key, text in cases:
        assert key.serialize() == text
        assert (
            key.serialize()
            == IntegrationTypeKey(
                key.protocol_id, key.task_type, key.mode_id
            ).serialize()
        )


def test_serialization_never_merges_parts_across_boundaries() -> None:
    """Verify keys differing only in part boundaries serialize differently."""
    first = IntegrationTypeKey(
        OpenIdentifier("a.b"), OpenIdentifier("c"), OpenIdentifier("d")
    )
    second = IntegrationTypeKey(
        OpenIdentifier("a"), OpenIdentifier("b.c"), OpenIdentifier("d")
    )

    assert first != second
    assert first.serialize() != second.serialize()
    assert first.serialize().split("/") == ["a.b", "c", "d"]
