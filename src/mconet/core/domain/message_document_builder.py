"""Fluent construction for validated immutable message documents."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal, Self, cast

from mconet.core.domain.extensions import Extensions
from mconet.core.domain.json_value import JsonValue
from mconet.core.domain.message_document import MessageDocument
from mconet.core.domain.message_document_validation import validate_message_document
from mconet.core.domain.message_group import MessageGroup


class MessageDocumentBuilder:
    """Accumulate document channels around one caller-supplied message root.

    Version, purpose, and root remain exact caller inputs. Metadata and
    extensions are independently snapshotted when supplied. Each :meth:`build`
    call creates a new immutable :class:`MessageDocument` and delegates complete
    tree, relation, ID, and JSON semantics to the existing document validator.

    The builder never creates or edits the message tree and is intentionally not
    thread-safe. Callers own group construction and should share only completed
    immutable documents across threads or tasks.
    """

    __slots__ = (
        "_extensions",
        "_metadata",
        "_purpose",
        "_root",
        "_version",
    )

    def __init__(
        self,
        version: str,
        purpose: Literal["input", "output", "context", "custom"],
        root: MessageGroup,
    ) -> None:
        """Start a builder with every required MessageDocument field.

        Args:
            version: Exact document format version text.
            purpose: Declared input, output, context, or custom purpose.
            root: Concrete caller-owned root message group.

        Raises:
            TypeError: If a required value has an invalid runtime shape.
        """
        candidate_version = cast(object, version)
        candidate_purpose = cast(object, purpose)
        candidate_root = cast(object, root)
        # Enforce only constructor storage shapes here. Non-empty version,
        # purpose membership, root Kind, and tree semantics remain validator-owned.
        if not isinstance(candidate_version, str):
            raise TypeError("MessageDocumentBuilder version must be a string.")
        if not isinstance(candidate_purpose, str):
            raise TypeError("MessageDocumentBuilder purpose must be a string.")
        if not isinstance(candidate_root, MessageGroup):
            raise TypeError("MessageDocumentBuilder root must be a MessageGroup.")

        # Required values are retained without normalization or tree copying.
        # Fresh mapping containers isolate every builder instance from others.
        self._version: str = candidate_version
        self._purpose: Literal["input", "output", "context", "custom"] = cast(
            Literal["input", "output", "context", "custom"], candidate_purpose
        )
        self._root: MessageGroup = candidate_root
        self._metadata: dict[str, JsonValue] = {}
        self._extensions: dict[str, JsonValue] = {}

    def with_metadata(self, metadata: Extensions) -> Self:
        """Replace document metadata with an owned mapping snapshot.

        Args:
            metadata: String-keyed descriptive JSON values.

        Returns:
            This builder for fluent construction.

        Raises:
            TypeError: If ``metadata`` is not a string-keyed mapping.
        """
        # Capture top-level membership now so caller changes cannot silently
        # alter a later document built from this construction state.
        self._metadata = _snapshot_mapping(metadata, "metadata")
        return self

    def with_extensions(self, extensions: Extensions) -> Self:
        """Replace unknown document fields with an owned mapping snapshot.

        Args:
            extensions: String-keyed forward-compatible JSON values.

        Returns:
            This builder for fluent construction.

        Raises:
            TypeError: If ``extensions`` is not a string-keyed mapping.
        """
        # Unknown fields stay separate from descriptive metadata and use their
        # own container so replacements cannot alias the other channel.
        self._extensions = _snapshot_mapping(extensions, "extensions")
        return self

    def build(self) -> MessageDocument:
        """Create and validate a new immutable message document.

        Returns:
            A fresh ``MessageDocument`` equivalent to direct construction with
            the builder's current fields.

        Raises:
            TypeError: If a dynamically supplied field has an invalid shape.
            ValueError: If document, tree, ID, relation, or JSON semantics are
                invalid.
        """
        # The immutable value snapshots both mappings while intentionally
        # retaining the exact root object and its already ordered element tree.
        document = MessageDocument(
            self._version,
            self._purpose,
            self._root,
            metadata=self._metadata,
            extensions=self._extensions,
        )
        # Reuse the document validator as the single semantic authority instead
        # of duplicating version, root, traversal, ID, relation, or JSON rules.
        return validate_message_document(document)


def _snapshot_mapping(value: Extensions, field_name: str) -> dict[str, JsonValue]:
    """Return an owned string-keyed mapping without interpreting JSON values."""
    candidate = cast(object, value)
    # Accept custom Mapping implementations while preserving the portable JSON
    # object requirement that every top-level key is a string.
    if not isinstance(candidate, Mapping):
        raise TypeError(f"MessageDocumentBuilder {field_name} must be a mapping.")
    source = cast(Mapping[object, object], candidate)
    if any(not isinstance(key, str) for key in source):
        raise TypeError(f"MessageDocumentBuilder {field_name} keys must be strings.")

    # Recursive JSON and numeric validation is deliberately deferred to build(),
    # keeping the existing MessageDocument validator as the semantic authority.
    return dict(cast(Mapping[str, JsonValue], source))
