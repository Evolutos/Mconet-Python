"""Semantic validation tests for immutable MessageGroup containers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal, cast

from mconet.core.domain import (
    Extensions,
    JsonValue,
    MessageContent,
    MessageElement,
    MessageElementKind,
    MessageEntry,
    MessageGroup,
    MessageRelation,
    OpenIdentifier,
    TextMessageContent,
    validate_message_group,
)


def _empty_extensions() -> Extensions:
    """Create independent extension storage for structural role fixtures."""
    # A fresh mapping for every role avoids shared mutable test state while still
    # satisfying the read-only public Mapping annotation.
    return {}


@dataclass(frozen=True, slots=True)
class _Kind:
    """Provide an open structural element Kind for group validation."""

    id: OpenIdentifier
    """Standard or provider-defined Kind identity."""

    category: str
    """Producer-defined classification category."""

    composition: Literal["leaf", "container"]
    """Tree composition checked by the Group validator."""


@dataclass(frozen=True, slots=True)
class _Role:
    """Provide a complete structural role for MessageEntry children."""

    id: OpenIdentifier
    """Open role identifier."""

    semantic: str | None = None
    """Optional producer description of the role meaning."""

    raw_value: str | None = None
    """Optional exact external role spelling."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Unknown role fields retained without interpretation."""


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected type and diagnostic fragment."""
    # A narrow exception boundary and message check prevent an unrelated earlier
    # failure from making a negative group scenario pass accidentally.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def _entry(entry_id: str, text: str = "text") -> MessageEntry:
    """Create one structurally valid entry child with one text content item."""
    # A caller-selected entry ID lets child identity tests vary independently
    # while every other MessageElement field remains ordinary and complete.
    return MessageEntry(
        entry_id,
        _Role(OpenIdentifier("message.user")),
        (TextMessageContent(f"{entry_id}-content", text),),
    )


def _container_kind(identifier: str = "message.history") -> MessageElementKind:
    """Return an open container Kind with a stable grouping category."""
    # Centralizing the valid baseline keeps tests focused on one changed field
    # without hiding any production behavior behind a mock.
    return _Kind(OpenIdentifier(identifier), "group", "container")


def _group(
    *,
    group_id: str = "history",
    kind: MessageElementKind | None = None,
    children: tuple[MessageElement, ...] | None = None,
    attributes: Extensions | None = None,
    value: JsonValue | None = None,
    relations: tuple[MessageRelation, ...] = (),
    metadata: Extensions | None = None,
    extensions: Extensions | None = None,
) -> MessageGroup:
    """Construct one valid group while exposing each validator input explicitly."""
    # None selects an independent default without conflating it with a deliberate
    # empty tuple or mapping supplied by a particular test scenario.
    selected_kind = kind if kind is not None else _container_kind()
    selected_children = children if children is not None else (_entry("entry-1"),)
    return MessageGroup(
        group_id,
        selected_kind,
        selected_children,
        attributes=attributes if attributes is not None else {},
        value=value,
        relations=relations,
        metadata=metadata if metadata is not None else {},
        extensions=extensions if extensions is not None else {},
    )


def _overwrite_field(
    group: MessageGroup, field_name: str, value: object
) -> MessageGroup:
    """Replace one frozen field to emulate a corrupted dynamic boundary value."""
    # Untyped deserializers can bypass annotations and frozen guards; object-level
    # assignment creates the same invalid state without weakening production code.
    object.__setattr__(group, field_name, value)
    return group


def _overwrite_entry_id(entry: MessageEntry, value: object) -> MessageEntry:
    """Replace a child entry ID to emulate an untyped deserialization result."""
    # The validator must narrow the observed child value even when a caller used
    # an object-level write to bypass the entry constructor's string check.
    object.__setattr__(entry, "id", value)
    return entry


def test_validator_accepts_open_container_and_preserves_child_order() -> None:
    """Verify standard and unknown container Kinds pass without rebuilding."""
    first = _entry("entry-1", "first")
    second = _entry("entry-2", "second")
    kind = _container_kind("vendor.timeline")
    group = _group(kind=kind, children=(first, second))
    original_children = group.sub_elements

    validated = validate_message_group(group)

    # Identity checks prove no Kind replacement, child sorting, tuple rebuilding,
    # or ID normalization occurs for a valid provider-defined container.
    assert validated is group
    assert validated.kind is kind
    assert validated.sub_elements is original_children
    assert tuple(child.id for child in validated.sub_elements) == (
        "entry-1",
        "entry-2",
    )


def test_validator_accepts_empty_group_and_case_distinct_child_ids() -> None:
    """Verify empty containers and case-sensitive direct identities remain valid."""
    empty = _group(children=())
    case_distinct = _group(children=(_entry("item"), _entry("Item")))

    # No architecture rule requires at least one child, and IDs remain exact
    # opaque strings rather than undergoing case folding or normalization.
    assert validate_message_group(empty) is empty
    assert validate_message_group(case_distinct) is case_distinct


def test_validator_rejects_non_group_and_invalid_group_ids() -> None:
    """Verify nominal type and unusable Group identity fail independently."""
    _assert_raises(
        TypeError,
        lambda: validate_message_group(cast(MessageGroup, object())),
        "must be a MessageGroup",
    )

    # Non-whitespace IDs remain opaque, while absence and all-whitespace values
    # cannot act as document-local identities for the container node.
    for value in ("", " \t"):
        _assert_raises(
            ValueError,
            lambda value=value: validate_message_group(_group(group_id=value)),
            "id must not be empty or whitespace",
        )


def test_validator_requires_open_container_kind() -> None:
    """Verify Kind syntax, category type, and composition fail at distinct fields."""
    cases: tuple[tuple[MessageElementKind, type[BaseException], str], ...] = (
        (
            _Kind(cast(OpenIdentifier, "message.history"), "group", "container"),
            TypeError,
            "kind id must be an OpenIdentifier",
        ),
        (
            _Kind(OpenIdentifier("Message.History"), "group", "container"),
            ValueError,
            "OpenIdentifier",
        ),
        (
            _Kind(
                OpenIdentifier("message.history"),
                cast(str, 1),
                "container",
            ),
            TypeError,
            "category must be a string",
        ),
        (
            _Kind(OpenIdentifier("message.history"), "group", "leaf"),
            ValueError,
            "composition must be container",
        ),
        (
            _Kind(
                OpenIdentifier("message.history"),
                "group",
                cast(Literal["leaf", "container"], 1),
            ),
            TypeError,
            "composition must be a string",
        ),
    )

    # Unknown valid Kind IDs are accepted by the success test. These cases cover
    # only malformed portable identity, field shape, and non-container semantics.
    for kind, exception_type, message in cases:
        _assert_raises(
            exception_type,
            lambda kind=kind: validate_message_group(_group(kind=kind)),
            message,
        )


def test_validator_enforces_direct_child_id_rules() -> None:
    """Verify child IDs are usable, distinct from the parent, and sibling-unique."""
    cases: tuple[tuple[tuple[MessageElement, ...], str], ...] = (
        ((_entry(""),), "child id must not be empty or whitespace"),
        ((_entry(" \t"),), "child id must not be empty or whitespace"),
        ((_entry("history"),), "child id must differ from group id"),
        (
            (_entry("entry-1", "first"), _entry("entry-1", "second")),
            "direct child ids must be unique",
        ),
    )

    # Each rule is evaluated against the direct ordered child tuple. Global
    # duplicates in separate branches remain a later document-level concern.
    for children, message in cases:
        _assert_raises(
            ValueError,
            lambda children=children: validate_message_group(_group(children=children)),
            message,
        )


def test_validator_rejects_non_string_direct_child_id() -> None:
    """Verify direct child identity is narrowed again at the Group boundary."""
    child = _overwrite_entry_id(_entry("entry-1"), 1)
    group = _group(children=(child,))

    # The child remains a complete MessageElement object, so the failure must be
    # attributed specifically to its dynamically corrupted identity field.
    _assert_raises(
        TypeError,
        lambda: validate_message_group(group),
        "child id must be a string",
    )


def test_validator_does_not_recursively_validate_child_payloads() -> None:
    """Verify child identity checks do not absorb Entry semantic validation."""
    invalid_entry = MessageEntry(
        "entry-1",
        _Role(OpenIdentifier("message.user")),
        (),
    )
    group = _group(children=(invalid_entry,))

    # The child has a usable unique ID but an empty content tuple. Group validation
    # succeeds because MessageDocument later composes Group and Entry validators.
    assert validate_message_group(group) is group


def test_validator_checks_generic_json_fields() -> None:
    """Verify attributes, value, metadata, and extensions use portable JSON rules."""
    cyclic: list[JsonValue] = []
    cyclic.append(cyclic)
    cases: tuple[tuple[MessageGroup, type[BaseException], str], ...] = (
        (
            _group(attributes={"invalid": cast(JsonValue, ("tuple",))}),
            TypeError,
            "JsonValue",
        ),
        (_group(value=cyclic), TypeError, "JsonValue"),
        (_group(metadata={"invalid": 2**53}), ValueError, "safe range"),
        (
            _group(extensions={"invalid": float("inf")}),
            ValueError,
            "finite",
        ),
    )

    # Each channel is independent and unknown keys remain legal; only recursive
    # shape and cross-language numeric portability are interpreted here.
    for group, exception_type, message in cases:
        _assert_raises(
            exception_type,
            lambda group=group: validate_message_group(group),
            message,
        )


def test_validator_rechecks_dynamically_corrupted_storage_shapes() -> None:
    """Verify frozen construction and static annotations are not blindly trusted."""
    cases: tuple[tuple[MessageGroup, str], ...] = (
        (_overwrite_field(_group(), "id", 1), "id must be a string"),
        (
            _overwrite_field(_group(), "kind", object()),
            "kind must implement MessageElementKind",
        ),
        (
            _overwrite_field(_group(), "name", 1),
            "name must be a string or None",
        ),
        (
            _overwrite_field(_group(), "sub_elements", []),
            "sub_elements must be a tuple",
        ),
        (
            _overwrite_field(_group(), "sub_elements", (object(),)),
            "sub_elements must contain MessageElement values",
        ),
        (
            _overwrite_field(_group(), "attributes", []),
            "attributes must be a mapping",
        ),
        (
            _overwrite_field(_group(), "value", object()),
            "JsonValue",
        ),
        (
            _overwrite_field(_group(), "relations", []),
            "relations must be a tuple",
        ),
        (
            _overwrite_field(_group(), "relations", (object(),)),
            "relations must contain MessageRelation values",
        ),
        (
            _overwrite_field(_group(), "metadata", []),
            "metadata must be a mapping",
        ),
        (
            _overwrite_field(_group(), "extensions", {1: True}),
            "extensions keys must be strings",
        ),
    )

    # Every damaged field reaches its own runtime guard, protecting consumers
    # even when an untyped boundary bypassed the ordinary immutable constructor.
    for group, message in cases:
        _assert_raises(
            TypeError,
            lambda group=group: validate_message_group(group),
            message,
        )


def test_validator_preserves_relation_order_without_resolving_endpoints() -> None:
    """Verify relation storage is checked while endpoint resolution stays deferred."""
    first = MessageRelation(
        "missing-source",
        "missing-target",
        OpenIdentifier("message.contains"),
    )
    second = MessageRelation(
        "history",
        "entry-1",
        OpenIdentifier("vendor.precedes"),
    )
    group = _group(relations=(first, second))

    # Missing endpoints do not fail without a document index, and successful
    # validation returns the same relation tuple in its declaration order.
    assert validate_message_group(group) is group
    assert group.relations == (first, second)
    assert group.relations[0] is first
    assert group.relations[1] is second


def test_validator_rejects_message_content_in_corrupted_children() -> None:
    """Verify MessageContent cannot cross into the element child collection."""
    content = TextMessageContent("content-1", "not an element")
    group = _overwrite_field(
        _group(),
        "sub_elements",
        (cast(MessageContent, content),),
    )

    # The dynamic overwrite bypasses constructor checks, so the Validator must
    # independently enforce the complete MessageElement child surface.
    _assert_raises(
        TypeError,
        lambda: validate_message_group(group),
        "sub_elements must contain MessageElement values",
    )
