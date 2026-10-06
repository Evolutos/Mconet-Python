"""Whole-tree semantic validation tests for MessageDocument values."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Literal, cast

from mconet.core.domain import (
    Extensions,
    JsonValue,
    MessageContent,
    MessageDocument,
    MessageElement,
    MessageElementKind,
    MessageElementValue,
    MessageEntry,
    MessageGroup,
    MessageRelation,
    OpenIdentifier,
    TextMessageContent,
    validate_message_document,
)

_DocumentPurpose = Literal["input", "output", "context", "custom"]


def _empty_extensions() -> Extensions:
    """Create independent extension storage for structural test fixtures."""
    # A fresh dictionary prevents one fixture's unknown data from affecting a
    # separate validation scenario through shared mutable defaults.
    return {}


@dataclass(frozen=True, slots=True)
class _Kind:
    """Provide an open structural Kind for concrete and custom elements."""

    id: OpenIdentifier
    """Standard or provider-defined element Kind identity."""

    category: str
    """Producer-defined classification category."""

    composition: Literal["leaf", "container"]
    """Tree composition used by whole-document traversal."""


@dataclass(frozen=True, slots=True)
class _Role:
    """Provide a complete structural role for MessageEntry fixtures."""

    id: OpenIdentifier
    """Open role identifier."""

    semantic: str | None = None
    """Optional producer description of the role meaning."""

    raw_value: str | None = None
    """Optional exact external role spelling."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Unknown role fields retained without interpretation."""


@dataclass(frozen=True, slots=True)
class _Element:
    """Represent a provider-defined open element without SDK inheritance."""

    id: str
    """Document-local element identifier."""

    kind: MessageElementKind
    """Open element classification."""

    name: str | None = None
    """Optional producer-defined element name."""

    attributes: Extensions = field(default_factory=_empty_extensions)
    """Kind-specific JSON attributes."""

    value: MessageElementValue | None = None
    """Optional generic JSON element value."""

    sub_elements: Sequence[MessageElement] = ()
    """Ordered child element sequence."""

    relations: Sequence[MessageRelation] = ()
    """Ordered directed relation sequence."""

    metadata: Extensions = field(default_factory=_empty_extensions)
    """Descriptive JSON metadata."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Unknown element fields retained for forward compatibility."""


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected type and diagnostic fragment."""
    # A narrow exception boundary and message assertion ensure the intended
    # document invariant, rather than an unrelated check, causes each failure.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def _entry(
    entry_id: str,
    content_id: str,
    *,
    text: str = "text",
    relations: tuple[MessageRelation, ...] = (),
) -> MessageEntry:
    """Create one valid text entry with caller-selected document-local IDs."""
    # IDs and relations remain explicit so global uniqueness and forward-reference
    # tests can vary one document fact without rebuilding unrelated fields.
    return MessageEntry(
        entry_id,
        _Role(OpenIdentifier("message.user")),
        (TextMessageContent(content_id, text),),
        relations=relations,
    )


def _group(
    group_id: str,
    kind_id: str,
    children: tuple[MessageElement, ...] = (),
    *,
    relations: tuple[MessageRelation, ...] = (),
) -> MessageGroup:
    """Create one concrete container Group with exact children and relations."""
    # Standard and unknown container IDs share the same open Kind implementation;
    # root-specific identity is decided by the Document validator.
    return MessageGroup(
        group_id,
        _Kind(OpenIdentifier(kind_id), "group", "container"),
        children,
        relations=relations,
    )


def _root(
    children: tuple[MessageElement, ...] = (),
    *,
    relations: tuple[MessageRelation, ...] = (),
) -> MessageGroup:
    """Create the standard root Group for a document fixture."""
    # A dedicated helper prevents ordinary tests from accidentally exercising a
    # non-root Kind when their focus is another document invariant.
    return _group("root", "message.root", children, relations=relations)


def _document(
    root: MessageGroup | None = None,
    *,
    version: str = "1.0",
    purpose: _DocumentPurpose = "input",
    metadata: Extensions | None = None,
    extensions: Extensions | None = None,
) -> MessageDocument:
    """Create one document with explicit override points for every public field."""
    # None selects independent defaults without conflating an intentionally empty
    # Mapping or root with absence in the test helper itself.
    return MessageDocument(
        version,
        purpose,
        root if root is not None else _root(),
        metadata=metadata if metadata is not None else {},
        extensions=extensions if extensions is not None else {},
    )


def _overwrite_field(value: object, field_name: str, replacement: object) -> object:
    """Replace one frozen field to emulate a corrupted dynamic boundary object."""
    # Untyped deserializers can bypass annotations and frozen guards; object-level
    # assignment creates that state without weakening production constructors.
    object.__setattr__(value, field_name, replacement)
    return value


def test_validator_accepts_multilevel_tree_and_forward_relations() -> None:
    """Verify complete validation preserves preorder and resolves forward edges."""
    forward = MessageRelation(
        "entry-1",
        "entry-2",
        OpenIdentifier("message.precedes"),
    )
    first = _entry("entry-1", "content-1", text="first", relations=(forward,))
    second = _entry("entry-2", "content-2", text="second")
    history = _group("history", "message.history", (first,))
    current = _group("current", "message.current", (second,))
    root = _root((history, current))
    document = _document(root)

    validated = validate_message_document(document)

    # Returning the same object and retaining every tuple prove traversal performs
    # no rebuilding, sorting, relation relocation, or text normalization.
    assert validated is document
    assert validated.root is root
    assert validated.root.sub_elements == (history, current)
    assert history.sub_elements == (first,)
    assert current.sub_elements == (second,)
    assert first.relations == (forward,)


def test_validator_accepts_all_purposes_and_future_nonempty_version() -> None:
    """Verify declared purposes and opaque future version text remain valid."""
    purposes: tuple[_DocumentPurpose, ...] = (
        "input",
        "output",
        "context",
        "custom",
    )

    # Version is intentionally not parsed as an undeclared format; exact nonempty
    # text remains available for future document revisions and compatibility policy.
    for purpose in purposes:
        document = _document(version="future-version", purpose=purpose)
        assert validate_message_document(document) is document
        assert document.version == "future-version"
        assert document.purpose == purpose


def test_validator_rejects_invalid_document_fields() -> None:
    """Verify nominal type, version, purpose, and root type fail independently."""
    _assert_raises(
        TypeError,
        lambda: validate_message_document(cast(MessageDocument, object())),
        "must be a MessageDocument",
    )
    cases: tuple[tuple[MessageDocument, type[BaseException], str], ...] = (
        (_document(version=""), ValueError, "version must not be empty"),
        (_document(version=" \t"), ValueError, "version must not be empty"),
        (
            cast(
                MessageDocument,
                _overwrite_field(_document(), "version", 1),
            ),
            TypeError,
            "version must be a string",
        ),
        (
            _document(purpose=cast(_DocumentPurpose, "vendor-purpose")),
            ValueError,
            "purpose must be input, output, context, or custom",
        ),
        (
            cast(
                MessageDocument,
                _overwrite_field(_document(), "purpose", 1),
            ),
            TypeError,
            "purpose must be a string",
        ),
        (
            cast(
                MessageDocument,
                _overwrite_field(_document(), "root", object()),
            ),
            TypeError,
            "root must be a MessageGroup",
        ),
    )

    # Dynamic corruption cases prove validation narrows observed runtime values
    # rather than trusting the constructor or static Literal annotation.
    for document, exception_type, message in cases:
        _assert_raises(
            exception_type,
            lambda document=document: validate_message_document(document),
            message,
        )


def test_validator_requires_standard_root_kind_and_container_semantics() -> None:
    """Verify only a valid message.root Group can anchor the document tree."""
    wrong_kind = _document(_group("root", "message.history"))
    leaf_root = _root()
    object.__setattr__(
        leaf_root,
        "kind",
        _Kind(OpenIdentifier("message.root"), "group", "leaf"),
    )

    # The general Group validator owns composition; the Document layer adds the
    # exact root Kind identity required for one unambiguous traversal entry point.
    _assert_raises(
        ValueError,
        lambda: validate_message_document(wrong_kind),
        "root kind must be message.root",
    )
    _assert_raises(
        ValueError,
        lambda: validate_message_document(_document(leaf_root)),
        "composition must be container",
    )


def test_validator_composes_nested_entry_and_group_validation() -> None:
    """Verify invalid concrete descendants fail through their dedicated validators."""
    empty_entry = MessageEntry(
        "entry-1",
        _Role(OpenIdentifier("message.user")),
        (),
    )
    invalid_group = _group("history", "message.history", (_entry("entry-2", "c2"),))
    object.__setattr__(
        invalid_group,
        "kind",
        _Kind(OpenIdentifier("message.history"), "group", "leaf"),
    )

    # Document traversal dispatches concrete nodes without copying their rules,
    # keeping Entry and Group validators as the sole owners of local semantics.
    _assert_raises(
        ValueError,
        lambda: validate_message_document(_document(_root((empty_entry,)))),
        "content must not be empty",
    )
    _assert_raises(
        ValueError,
        lambda: validate_message_document(_document(_root((invalid_group,)))),
        "composition must be container",
    )


def test_validator_supports_open_leaf_and_container_elements() -> None:
    """Verify provider-defined elements participate in the same ordered tree."""
    leaf = _Element(
        "custom-leaf",
        _Kind(OpenIdentifier("vendor.note"), "vendor.note", "leaf"),
        value={"text": "note"},
    )
    container = _Element(
        "custom-container",
        _Kind(OpenIdentifier("vendor.section"), "vendor.group", "container"),
        sub_elements=[leaf],
    )
    document = _document(_root((container,)))

    # Custom mutable Sequence storage is snapshotted for validation, but the
    # producer objects and open Kind values remain unchanged and unregistered.
    assert validate_message_document(document) is document
    assert container.sub_elements == [leaf]
    assert leaf.kind.id.value == "vendor.note"


def test_validator_rejects_invalid_open_element_composition_and_json() -> None:
    """Verify open elements cannot hide children or malformed JSON data."""
    child = _Element(
        "child",
        _Kind(OpenIdentifier("vendor.child"), "vendor.note", "leaf"),
    )
    leaf_with_child = _Element(
        "parent",
        _Kind(OpenIdentifier("vendor.parent"), "vendor.note", "leaf"),
        sub_elements=(child,),
    )
    invalid_json = _Element(
        "invalid-json",
        _Kind(OpenIdentifier("vendor.note"), "vendor.note", "leaf"),
        metadata={"invalid": cast(JsonValue, ("tuple",))},
    )

    _assert_raises(
        ValueError,
        lambda: validate_message_document(_document(_root((leaf_with_child,)))),
        "leaf sub_elements must be empty",
    )
    _assert_raises(
        TypeError,
        lambda: validate_message_document(_document(_root((invalid_json,)))),
        "JsonValue",
    )


def test_validator_enforces_one_global_element_and_content_id_namespace() -> None:
    """Verify duplicates across branches, content, and element domains all fail."""
    duplicate_elements = _document(
        _root(
            (
                _group("left", "vendor.group", (_entry("same", "content-1"),)),
                _group("right", "vendor.group", (_entry("same", "content-2"),)),
            )
        )
    )
    duplicate_content = _document(
        _root(
            (
                _group("left", "vendor.group", (_entry("entry-1", "same"),)),
                _group("right", "vendor.group", (_entry("entry-2", "same"),)),
            )
        )
    )
    cross_domain = _document(_root((_entry("entry-1", "root"),)))

    # Direct sibling duplicates are already rejected by Group validation; these
    # cases specifically prove document-wide and cross-domain uniqueness.
    for document in (duplicate_elements, duplicate_content, cross_domain):
        _assert_raises(
            ValueError,
            lambda document=document: validate_message_document(document),
            "element and content ids must be unique",
        )


def test_validator_rejects_unusable_content_ids_and_element_content_overlap() -> None:
    """Verify content IDs are usable and MessageElement values never become content."""
    empty_content_id = _document(_root((_entry("entry-1", ""),)))
    group_as_content = _group("embedded-group", "vendor.group")
    entry = MessageEntry(
        "entry-2",
        _Role(OpenIdentifier("message.user")),
        (cast(MessageContent, group_as_content),),
    )

    _assert_raises(
        ValueError,
        lambda: validate_message_document(empty_content_id),
        "content id must not be empty",
    )
    _assert_raises(
        ValueError,
        lambda: validate_message_document(_document(_root((entry,)))),
        "content must not contain MessageElement values",
    )


def test_validator_resolves_relations_only_against_element_ids() -> None:
    """Verify forward references pass while absent or content endpoints fail."""
    valid = MessageRelation(
        "entry-1",
        "entry-2",
        OpenIdentifier("message.precedes"),
    )
    missing_source = MessageRelation(
        "missing",
        "entry-2",
        OpenIdentifier("message.precedes"),
    )
    missing_target = MessageRelation(
        "entry-1",
        "missing",
        OpenIdentifier("message.precedes"),
    )
    content_target = MessageRelation(
        "entry-1",
        "content-2",
        OpenIdentifier("message.precedes"),
    )
    second = _entry("entry-2", "content-2")

    def _with_relation(relation: MessageRelation) -> MessageDocument:
        """Build the same two-entry tree with one caller-selected relation."""
        # A stable topology isolates endpoint resolution from unrelated tree or
        # content differences across the four relation scenarios.
        first = _entry("entry-1", "content-1", relations=(relation,))
        return _document(_root((first, second)))

    assert validate_message_document(_with_relation(valid)) is not None
    _assert_raises(
        ValueError,
        lambda: validate_message_document(_with_relation(missing_source)),
        "source must reference an element id",
    )
    for relation in (missing_target, content_target):
        _assert_raises(
            ValueError,
            lambda relation=relation: validate_message_document(
                _with_relation(relation)
            ),
            "target must reference an element id",
        )


def test_validator_checks_relation_shape_after_dynamic_corruption() -> None:
    """Verify relation fields are narrowed again before endpoint resolution."""
    invalid_type = MessageRelation(
        "entry-1",
        "entry-2",
        OpenIdentifier("message.precedes"),
    )
    object.__setattr__(invalid_type, "type", OpenIdentifier("Message.Precedes"))
    invalid_metadata = MessageRelation(
        "entry-1",
        "entry-2",
        OpenIdentifier("message.precedes"),
    )
    object.__setattr__(invalid_metadata, "metadata", {"invalid": float("inf")})
    second = _entry("entry-2", "content-2")

    def _with_relation(relation: MessageRelation) -> MessageDocument:
        """Build a complete tree containing one dynamically damaged relation."""
        # Both endpoints exist so shape or metadata errors occur before no other
        # missing-reference condition can obscure the intended failure.
        first = _entry("entry-1", "content-1", relations=(relation,))
        return _document(_root((first, second)))

    _assert_raises(
        ValueError,
        lambda: validate_message_document(_with_relation(invalid_type)),
        "OpenIdentifier",
    )
    _assert_raises(
        ValueError,
        lambda: validate_message_document(_with_relation(invalid_metadata)),
        "finite",
    )


def test_validator_rejects_cycles_without_recursive_overflow() -> None:
    """Verify an indirect Group cycle receives a stable semantic failure."""
    first = _group("first", "vendor.group")
    second = _group("second", "vendor.group")
    object.__setattr__(first, "sub_elements", (second,))
    object.__setattr__(second, "sub_elements", (first,))
    document = _document(_root((first,)))

    # Distinct IDs avoid local parent/child collisions, forcing the traversal's
    # active-object cycle detector to identify the indirect object graph cycle.
    _assert_raises(
        ValueError,
        lambda: validate_message_document(document),
        "tree must not contain cycles",
    )


def test_validator_handles_deep_tree_iteratively() -> None:
    """Verify valid nesting does not depend on Python's recursion limit."""
    element: MessageElement = _entry("entry-0", "content-0")
    for index in range(1, 1_500):
        element = _Element(
            f"container-{index}",
            _Kind(OpenIdentifier("vendor.container"), "vendor.group", "container"),
            sub_elements=(element,),
        )
    document = _document(_root((element,)))

    # Iterative enter/leave frames validate all 1,500 levels without changing the
    # process recursion limit or raising RecursionError.
    assert validate_message_document(document) is document


def test_validator_checks_document_json_channels() -> None:
    """Verify metadata and extensions reject malformed recursive JSON values."""
    cyclic: list[JsonValue] = []
    cyclic.append(cyclic)
    cases: tuple[tuple[MessageDocument, type[BaseException], str], ...] = (
        (
            _document(metadata={"invalid": cast(JsonValue, ("tuple",))}),
            TypeError,
            "JsonValue",
        ),
        (_document(metadata={"invalid": cyclic}), TypeError, "JsonValue"),
        (_document(extensions={"invalid": 2**53}), ValueError, "safe range"),
        (
            _document(extensions={"invalid": float("inf")}),
            ValueError,
            "finite",
        ),
    )

    # Unknown keys remain legal and separate; only recursive shape and portable
    # number semantics are interpreted at the document trust boundary.
    for document, exception_type, message in cases:
        _assert_raises(
            exception_type,
            lambda document=document: validate_message_document(document),
            message,
        )
