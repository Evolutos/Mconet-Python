"""Field and ownership tests for immutable TextMessageContent values."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import FrozenInstanceError
from typing import cast

from mconet.core.domain import (
    Extensions,
    JsonValue,
    MessageContent,
    MessageContentKind,
    MessageElement,
    TextMessageContent,
)


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    # Keep the exception boundary narrow so unexpected success or failure types
    # remain visible instead of being absorbed by test control flow.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def _mutate_mapping(mapping: dict[str, JsonValue]) -> None:
    """Attempt one item assignment through a dynamically narrowed mapping."""
    # Crossing the static read-only boundary deliberately proves the mapping
    # proxy enforces the same ownership rule at runtime.
    mapping["changed"] = True


def test_text_message_content_has_fixed_kind_and_exact_text() -> None:
    """Verify text content satisfies its protocol with a fixed standard kind."""
    text = "第一行 👋\nsecond line"
    content = TextMessageContent("content-1", text)
    contract: MessageContent = content

    # Text remains byte-for-byte equivalent at the string level, while the Kind
    # is supplied by the concrete type and static protocol conformance requires
    # no adapter or caller-provided Kind object.
    assert isinstance(content, MessageContent)
    assert isinstance(content.kind, MessageContentKind)
    assert contract.id == "content-1"
    assert content.text == text
    assert content.kind.id.value == "content.text"
    assert content.metadata == {}
    assert content.extensions == {}


def test_text_message_content_kind_views_cannot_change_the_fixed_kind() -> None:
    """Verify mutation of one dynamic kind view cannot affect later reads."""
    content = TextMessageContent("content-1", "Hello")
    first_view = content.kind

    # The protocol exposes id as read-only, but force a dynamic mutation to prove
    # the concrete content returns an isolated view instead of shared state.
    object.__setattr__(first_view, "id", first_view.id.__class__("vendor.changed"))
    second_view = content.kind

    assert first_view.id.value == "vendor.changed"
    assert second_view.id.value == "content.text"
    assert second_view is not first_view


def test_text_message_content_snapshots_data_and_is_immutable() -> None:
    """Verify mapping membership and dataclass fields cannot change after creation."""
    metadata: dict[str, JsonValue] = {"language": "zh-CN"}
    extensions: dict[str, JsonValue] = {"vendorField": {"version": 1}}
    content = TextMessageContent(
        "content-1",
        "Hello",
        metadata=metadata,
        extensions=extensions,
    )

    # Caller-owned membership changes do not leak into the content, and both the
    # frozen dataclass and mapping proxies reject mutation through public fields.
    metadata["language"] = "en"
    extensions["other"] = False
    assert content.metadata == {"language": "zh-CN"}
    assert content.extensions == {"vendorField": {"version": 1}}
    _assert_raises(
        FrozenInstanceError,
        lambda: content.__setattr__("text", "changed"),
        "cannot assign to field",
    )
    _assert_raises(
        TypeError,
        lambda: _mutate_mapping(cast(dict[str, JsonValue], content.metadata)),
        "does not support item assignment",
    )


def test_text_message_content_has_no_element_or_task_fields() -> None:
    """Verify the concrete content remains outside tree and task configuration."""
    content = TextMessageContent("content-1", "Hello")
    parameters = tuple(inspect.signature(TextMessageContent).parameters)

    # The constructor contains only content identity, payload, and shared JSON
    # data. Kind is fixed, and neither element-tree nor generation fields appear.
    assert parameters == ("id", "text", "metadata", "extensions")
    assert not isinstance(content, MessageElement)
    assert not hasattr(content, "sub_elements")
    assert not hasattr(content, "relations")
    assert not hasattr(content, "temperature")
    assert not hasattr(content, "max_tokens")
    assert not hasattr(content, "stop")


def test_text_message_content_rejects_invalid_storage_shapes() -> None:
    """Verify dynamic callers cannot bypass primitive and mapping field types."""
    # Only storage shapes are checked here; semantic text cases and length limits
    # remain deliberately outside this definition for the dedicated validator.
    _assert_raises(
        TypeError,
        lambda: TextMessageContent(cast(str, 1), "text"),
        "id must be a string",
    )
    _assert_raises(
        TypeError,
        lambda: TextMessageContent("content-1", cast(str, 1)),
        "text must be a string",
    )
    _assert_raises(
        TypeError,
        lambda: TextMessageContent("content-1", "text", metadata=cast(Extensions, [])),
        "metadata must be a mapping",
    )
    _assert_raises(
        TypeError,
        lambda: TextMessageContent(
            "content-1",
            "text",
            extensions=cast(Extensions, {1: "value"}),
        ),
        "extensions keys must be strings",
    )
