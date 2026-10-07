"""Atomic composition tests for immutable message mapping results."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import FrozenInstanceError, dataclass, fields
from typing import Literal, cast

from mconet.core.domain import (
    ArtifactCatalog,
    MessageDocument,
    MessageGroup,
    OpenIdentifier,
)
from mconet.core.spi import MessageMappingResult


@dataclass(frozen=True, slots=True)
class _RootKind:
    """Provide the complete structural Kind for a mapped root group."""

    id: OpenIdentifier
    """Standard message-root identifier."""

    category: str
    """Root grouping category retained by the document."""

    composition: Literal["leaf", "container"]
    """Container composition required for a document root."""


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise one expected exception and message fragment."""
    try:
        action()
    except exception_type as error:
        # Match result-owned wording so an unrelated fixture failure cannot make
        # a nominal pair-boundary test appear successful.
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def _document(
    purpose: Literal["input", "output", "context", "custom"] = "output",
) -> MessageDocument:
    """Build one complete empty message document for mapper-result fixtures."""
    # The concrete document keeps fixture construction on the public production
    # path while an empty tree leaves these tests focused on result composition.
    root = MessageGroup(
        "root",
        _RootKind(OpenIdentifier("message.root"), "group", "container"),
        (),
    )
    return MessageDocument("1.0", purpose, root)


def test_message_mapping_result_preserves_atomic_pair_identity() -> None:
    """Keep the exact mapped document and its artifact catalog together."""
    document = _document()
    artifacts = ArtifactCatalog()

    result = MessageMappingResult(document, artifacts)

    # Identity preservation prevents the result from rebuilding the document,
    # substituting another catalog, or silently dropping an explicit empty scope.
    assert result.document is document
    assert result.artifacts is artifacts
    assert result.artifacts.artifacts == ()


def test_message_mapping_result_has_exact_required_field_surface() -> None:
    """Expose only the two required values with no partial-result state."""
    result = MessageMappingResult(_document(), ArtifactCatalog())

    # The exact constructor surface makes both values mandatory and excludes
    # decoded payloads, task results, diagnostics, transport data, and registries.
    assert tuple(field.name for field in fields(MessageMappingResult)) == (
        "document",
        "artifacts",
    )
    assert tuple(inspect.signature(MessageMappingResult).parameters) == (
        "document",
        "artifacts",
    )
    assert not hasattr(result, "payload")
    assert not hasattr(result, "task_result")
    assert not hasattr(result, "diagnostics")
    assert not hasattr(result, "transport_response")
    assert not hasattr(result, "artifact_registry")


def test_message_mapping_result_is_frozen_and_value_comparable() -> None:
    """Reject pair replacement and compare results by their complete values."""
    document = _document()
    artifacts = ArtifactCatalog()
    first = MessageMappingResult(document, artifacts)
    same = MessageMappingResult(document, artifacts)
    different = MessageMappingResult(_document("context"), artifacts)

    # Frozen storage prevents a monitor or caller from swapping the catalog away
    # from the document after mapper completion; equality has no hidden state.
    assert first == same
    assert first != different
    _assert_raises(
        FrozenInstanceError,
        lambda: first.__setattr__("artifacts", ArtifactCatalog()),
        "cannot assign to field",
    )


def test_message_mapping_result_requires_message_document() -> None:
    """Reject a tree root that omits the complete document boundary."""
    root = _document().root

    # A MessageGroup alone lacks version, purpose, metadata, extensions, and the
    # complete document-local validation scope required by response mapping.
    _assert_raises(
        TypeError,
        lambda: MessageMappingResult(
            cast(MessageDocument, root),
            ArtifactCatalog(),
        ),
        "document must be a MessageDocument",
    )


def test_message_mapping_result_requires_explicit_artifact_catalog() -> None:
    """Reject absent and bare collection substitutes for artifact scope."""
    document = _document()

    # An explicit empty Catalog represents a completed mapping with no artifacts;
    # None or tuple instead indicates that the mapper failed to return its scope.
    for invalid in (None, ()):
        _assert_raises(
            TypeError,
            lambda invalid=invalid: MessageMappingResult(
                document,
                cast(ArtifactCatalog, invalid),
            ),
            "artifacts must be an ArtifactCatalog",
        )
