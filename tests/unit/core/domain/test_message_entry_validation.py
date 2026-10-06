"""Semantic validation tests for immutable MessageEntry leaf elements."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal, cast

from mconet.core.domain import (
    Extensions,
    JsonValue,
    MessageContent,
    MessageContentKind,
    MessageElement,
    MessageElementKind,
    MessageElementValue,
    MessageEntry,
    MessageRole,
    OpenIdentifier,
    TextMessageContent,
    validate_message_entry,
)


def _empty_extensions() -> Extensions:
    """Create independent extension storage for structural test fixtures."""
    # Each fixture owns its dictionary so a mutation in one negative case cannot
    # change another case or make test results depend on execution order.
    return {}


@dataclass(frozen=True, slots=True)
class _Role:
    """Provide an open structural role for validator scenarios."""

    id: OpenIdentifier
    """Standard or unknown role identity."""

    semantic: str | None = None
    """Optional producer description of the role meaning."""

    raw_value: str | None = None
    """Optional exact external role spelling."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Unknown role fields preserved as portable JSON data."""


@dataclass(frozen=True, slots=True)
class _ElementKind:
    """Supply a dynamic entry Kind for fixed-invariant failure tests."""

    id: OpenIdentifier
    """Open element-kind identifier under validation."""

    category: str
    """Producer-supplied element category under validation."""

    composition: Literal["leaf", "container"]
    """Tree composition used to exercise leaf enforcement."""


@dataclass(frozen=True, slots=True)
class _ContentKind:
    """Supply the open Kind of a custom message content fixture."""

    id: OpenIdentifier
    """Open content-kind identifier retained without a known-kind registry."""


@dataclass(frozen=True, slots=True)
class _UnknownContent:
    """Represent valid future content without inheriting an SDK implementation."""

    id: str
    """Document-local content identifier."""

    kind: MessageContentKind
    """Open content classification."""

    metadata: Extensions = field(default_factory=_empty_extensions)
    """Descriptive content metadata."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Unknown content fields preserved for forward compatibility."""


class _KindOverrideEntry(MessageEntry):
    """Return a caller-selected Kind from an otherwise valid entry."""

    override_kind: MessageElementKind
    """Dynamic Kind supplied after normal base construction."""

    def __init__(self, kind: MessageElementKind) -> None:
        """Build a valid base entry and retain the Kind used by the override."""
        # Base construction supplies every immutable field before object-level
        # assignment installs only the test override on this dynamic subclass.
        super().__init__(
            "entry-1",
            _Role(OpenIdentifier("message.user")),
            (TextMessageContent("content-1", "Hello"),),
        )
        object.__setattr__(self, "override_kind", kind)

    @property
    def kind(self) -> MessageElementKind:
        """Return the test-selected Kind instead of the fixed entry Kind."""
        # This deliberate override proves validation does not trust the concrete
        # type's normal property implementation at an external trust boundary.
        return self.override_kind


class _ChildBearingEntry(MessageEntry):
    """Expose one child from a Kind that still claims leaf composition."""

    @property
    def sub_elements(self) -> tuple[()]:
        """Return the entry itself as a non-empty child sequence."""
        # Preserve the base signature for static substitutability, then inject a
        # dynamically invalid value to exercise the runtime trust boundary.
        return cast(tuple[()], (cast(MessageElement, self),))


class _NamedEntry(MessageEntry):
    """Expose a forbidden generic name from an otherwise valid entry."""

    @property
    def name(self) -> None:
        """Return a generic label that conflicts with fixed entry semantics."""
        # The cast keeps the override signature compatible while deliberately
        # presenting an invalid runtime value to the validator.
        return cast(None, "unexpected")


class _AttributedEntry(MessageEntry):
    """Expose forbidden generic attributes from an otherwise valid entry."""

    @property
    def attributes(self) -> Extensions:
        """Return one generic attribute that entries must not carry."""
        # Entry-specific data belongs to explicit fields, so this extra channel
        # must be rejected even though its JSON value is otherwise portable.
        return {"unexpected": True}


class _ValuedEntry(MessageEntry):
    """Expose a forbidden generic value from an otherwise valid entry."""

    @property
    def value(self) -> None:
        """Return a JSON payload that bypasses the content collection."""
        # A direct value would create a second payload path outside Content; the
        # cast retains the base signature solely for this runtime failure case.
        return cast(None, cast(MessageElementValue, {"unexpected": True}))


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected type and diagnostic fragment."""
    # A narrow boundary and message check ensure the intended field fails rather
    # than an unrelated earlier check accidentally satisfying the negative case.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def _valid_entry(**overrides: object) -> MessageEntry:
    """Construct one valid entry while allowing explicit field replacements."""
    arguments: dict[str, object] = {
        "id": "entry-1",
        "role": _Role(OpenIdentifier("message.user")),
        "content": (
            TextMessageContent("content-1", "first"),
            TextMessageContent("content-2", "second"),
        ),
    }
    # Updating a fresh dictionary keeps each scenario isolated while centralizing
    # only the ordinary valid baseline needed by many independent assertions.
    arguments.update(overrides)
    return MessageEntry(
        id=cast(str, arguments["id"]),
        role=cast(MessageRole, arguments["role"]),
        content=cast(tuple[MessageContent, ...], arguments["content"]),
        metadata=cast(Extensions, arguments.get("metadata", {})),
        extensions=cast(Extensions, arguments.get("extensions", {})),
    )


def _overwrite_field(
    entry: MessageEntry, field_name: str, value: object
) -> MessageEntry:
    """Replace one frozen field to emulate a corrupted dynamic boundary value."""
    # Deserializers and untyped callers can bypass annotations or frozen guards;
    # object-level assignment creates that state without weakening production code.
    object.__setattr__(entry, field_name, value)
    return entry


def test_validator_accepts_standard_text_entry_without_reordering() -> None:
    """Verify a valid text entry passes by identity with exact content order."""
    entry = _valid_entry()
    original_content = entry.content

    validated = validate_message_entry(entry)

    # Identity and tuple equality prove validation performs no rebuilding,
    # normalization, role substitution, or content sorting.
    assert validated is entry
    assert validated.content is original_content
    assert tuple(item.id for item in validated.content) == (
        "content-1",
        "content-2",
    )


def test_validator_preserves_unknown_role_and_open_content() -> None:
    """Verify domain validation remains open before later runtime scope checks."""
    role = _Role(
        OpenIdentifier("vendor.moderator"),
        semantic="Reviews the response.",
        raw_value="Moderator",
        extensions={"vendor.policy": "quality"},
    )
    content = _UnknownContent(
        "content-1",
        _ContentKind(OpenIdentifier("vendor.rich_text")),
        metadata={"language": "zh-CN"},
        extensions={"vendor.style": {"emphasis": True}},
    )
    entry = _valid_entry(role=role, content=(content,))

    # This validator owns domain shape, not release support. Both unknown values
    # stay exact for the dedicated later scope check and protocol adapter.
    assert validate_message_entry(entry) is entry
    assert entry.role is role
    assert entry.content == (content,)


def test_validator_rejects_non_entry_and_unusable_identity() -> None:
    """Verify nominal type and document-local entry identity fail independently."""
    _assert_raises(
        TypeError,
        lambda: validate_message_entry(cast(MessageEntry, object())),
        "must be a MessageEntry",
    )

    # Entry identifiers are opaque and remain untrimmed, but empty or entirely
    # whitespace strings cannot serve as document-local element keys.
    for value in ("", " \t"):
        _assert_raises(
            ValueError,
            lambda value=value: validate_message_entry(_valid_entry(id=value)),
            "id must not be empty or whitespace",
        )


def test_validator_rejects_container_kind_and_non_empty_children() -> None:
    """Verify both Kind composition and actual children enforce leaf semantics."""
    container = _KindOverrideEntry(
        _ElementKind(OpenIdentifier("message.entry"), "entry", "container")
    )
    child_bearing = _ChildBearingEntry(
        "entry-1",
        _Role(OpenIdentifier("message.user")),
        (TextMessageContent("content-1", "Hello"),),
    )

    # A container declaration and a hidden child are distinct ways to violate
    # leaf behavior; each receives a stable field-specific diagnostic.
    _assert_raises(
        ValueError,
        lambda: validate_message_entry(container),
        "composition must be leaf",
    )
    _assert_raises(
        ValueError,
        lambda: validate_message_entry(child_bearing),
        "sub_elements must be empty for a leaf",
    )


def test_validator_rejects_wrong_fixed_kind_fields() -> None:
    """Verify valid open values cannot reclassify a concrete MessageEntry."""
    cases = (
        (
            _ElementKind(OpenIdentifier("vendor.entry"), "entry", "leaf"),
            "kind id must be message.entry",
        ),
        (
            _ElementKind(OpenIdentifier("message.entry"), "vendor.entry", "leaf"),
            "kind category must be entry",
        ),
    )

    # Open element kinds are valid elsewhere, but this nominal concrete type has
    # one exact identity and category so mapper selection stays unambiguous.
    for kind, message in cases:
        _assert_raises(
            ValueError,
            lambda kind=kind: validate_message_entry(_KindOverrideEntry(kind)),
            message,
        )


def test_validator_rejects_generic_entry_data_channels() -> None:
    """Verify name, attributes, and value cannot bypass explicit entry fields."""
    role = _Role(OpenIdentifier("message.user"))
    content = (TextMessageContent("content-1", "Hello"),)
    cases: tuple[tuple[MessageEntry, str], ...] = (
        (_NamedEntry("entry-1", role, content), "name must be None"),
        (
            _AttributedEntry("entry-1", role, content),
            "attributes must be empty",
        ),
        (_ValuedEntry("entry-1", role, content), "value must be None"),
    )

    # Each dynamic override remains a nominal MessageEntry, proving the validator
    # checks observed runtime values instead of trusting the base implementation.
    for entry, message in cases:
        _assert_raises(
            ValueError,
            lambda entry=entry: validate_message_entry(entry),
            message,
        )


def test_validator_rejects_empty_content() -> None:
    """Verify a message entry cannot exist without at least one content item."""
    entry = _valid_entry(content=())
    empty_text_entry = _valid_entry(content=(TextMessageContent("content-1", ""),))

    # Empty text remains valid when one content item exists. An absent content
    # item is a separate entry-level semantic condition and fails independently.
    assert validate_message_entry(empty_text_entry) is empty_text_entry
    _assert_raises(
        ValueError,
        lambda: validate_message_entry(entry),
        "content must not be empty",
    )


def test_validator_rechecks_dynamically_corrupted_storage_shapes() -> None:
    """Verify annotations and frozen construction are not trusted at validation."""
    cases: tuple[tuple[MessageEntry, str], ...] = (
        (_overwrite_field(_valid_entry(), "id", 1), "id must be a string"),
        (
            _overwrite_field(_valid_entry(), "role", object()),
            "role must implement MessageRole",
        ),
        (
            _overwrite_field(_valid_entry(), "content", []),
            "content must be a tuple",
        ),
        (
            _overwrite_field(_valid_entry(), "content", ("text",)),
            "content must contain MessageContent values",
        ),
        (
            _overwrite_field(_valid_entry(), "relations", []),
            "relations must be a tuple",
        ),
        (
            _overwrite_field(_valid_entry(), "relations", ("relation",)),
            "relations must contain MessageRelation values",
        ),
        (
            _overwrite_field(_valid_entry(), "metadata", []),
            "metadata must be a mapping",
        ),
        (
            _overwrite_field(_valid_entry(), "extensions", {1: True}),
            "extensions keys must be strings",
        ),
    )

    # Every malformed runtime value reaches its own field-specific guard, which
    # protects consumers even when object construction was bypassed dynamically.
    for entry, message in cases:
        _assert_raises(
            TypeError,
            lambda entry=entry: validate_message_entry(entry),
            message,
        )


def test_validator_delegates_invalid_role_semantics() -> None:
    """Verify malformed role identity and extension JSON fail predictably."""
    cases: tuple[tuple[MessageRole, type[BaseException], str], ...] = (
        (_Role(OpenIdentifier("Message.User")), ValueError, "OpenIdentifier"),
        (
            _Role(
                OpenIdentifier("message.user"),
                extensions={"invalid": cast(JsonValue, ("tuple",))},
            ),
            TypeError,
            "JsonValue",
        ),
    )

    # The shared Role validator remains the only owner of open identifier and
    # role extension semantics, avoiding a divergent entry-specific rule set.
    for role, exception_type, message in cases:
        _assert_raises(
            exception_type,
            lambda role=role: validate_message_entry(_valid_entry(role=role)),
            message,
        )


def test_validator_checks_known_and_unknown_content_semantics() -> None:
    """Verify concrete text and open content use their appropriate validators."""
    invalid_text = TextMessageContent(
        "content-1",
        "Hello",
        metadata={"invalid": 2**53},
    )
    invalid_unknown_kind = _UnknownContent(
        "content-2",
        _ContentKind(OpenIdentifier("Vendor.RichText")),
    )
    invalid_unknown_json = _UnknownContent(
        "content-3",
        _ContentKind(OpenIdentifier("vendor.rich_text")),
        extensions={"invalid": float("inf")},
    )
    cases: tuple[tuple[MessageContent, type[BaseException], str], ...] = (
        (invalid_text, ValueError, "safe range"),
        (invalid_unknown_kind, ValueError, "OpenIdentifier"),
        (invalid_unknown_json, ValueError, "finite"),
    )

    # Text-specific errors come from its concrete validator; unknown content is
    # checked only against shared portable fields and is not rejected by kind.
    for content, exception_type, message in cases:
        _assert_raises(
            exception_type,
            lambda content=content: validate_message_entry(
                _valid_entry(content=(content,))
            ),
            message,
        )


def test_validator_checks_entry_metadata_and_extensions() -> None:
    """Verify both entry JSON channels reject malformed recursive values."""
    cyclic: list[JsonValue] = []
    cyclic.append(cyclic)
    cases: tuple[tuple[str, JsonValue, type[BaseException], str], ...] = (
        ("metadata", cast(JsonValue, ("tuple",)), TypeError, "JsonValue"),
        ("metadata", cyclic, TypeError, "JsonValue"),
        ("extensions", 2**53, ValueError, "safe range"),
        ("extensions", float("inf"), ValueError, "finite"),
    )

    # Construction snapshots membership but deliberately defers recursive JSON
    # rules, so each channel reaches this validator with its malformed value.
    for field_name, value, exception_type, message in cases:
        entry = _valid_entry(**{field_name: {"invalid": value}})
        _assert_raises(
            exception_type,
            lambda entry=entry: validate_message_entry(entry),
            message,
        )
