"""Fluent construction for validated immutable message entries."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Self, cast

from mconet.core.domain.extensions import Extensions
from mconet.core.domain.json_value import JsonValue
from mconet.core.domain.message_content import MessageContent
from mconet.core.domain.message_entry import MessageEntry
from mconet.core.domain.message_entry_validation import validate_message_entry
from mconet.core.domain.message_relation import MessageRelation
from mconet.core.domain.message_role import MessageRole


class MessageEntryBuilder:
    """Accumulate fields for one validated immutable ``MessageEntry``.

    The builder owns independent mutable collections for one construction flow.
    Content and relations retain insertion order, while metadata and extensions
    are snapshotted when supplied. Each :meth:`build` call creates a new value
    and delegates all domain semantics to :func:`validate_message_entry`.

    The builder is intentionally not thread-safe. Callers should keep one
    instance within a single construction flow and share only built immutable
    entries across threads or tasks.
    """

    __slots__ = (
        "_content",
        "_entry_id",
        "_extensions",
        "_metadata",
        "_relations",
        "_role",
    )

    def __init__(self, entry_id: str, role: MessageRole) -> None:
        """Start a builder with the two required entry identity fields.

        Args:
            entry_id: Document-local identifier retained without normalization.
            role: Structural message role retained by identity.

        Raises:
            TypeError: If either required value has an invalid runtime shape.
        """
        candidate_id = cast(object, entry_id)
        candidate_role = cast(object, role)
        # Reject storage-shape errors before creating mutable builder state, but
        # leave non-empty ID and role semantics to the shared domain validator.
        if not isinstance(candidate_id, str):
            raise TypeError("MessageEntryBuilder entry_id must be a string.")
        if not isinstance(candidate_role, MessageRole):
            raise TypeError("MessageEntryBuilder role must implement MessageRole.")

        # Every instance receives fresh containers, preventing one construction
        # flow from observing content or metadata added through another builder.
        self._entry_id = candidate_id
        self._role = candidate_role
        self._content: list[MessageContent] = []
        self._relations: list[MessageRelation] = []
        self._metadata: dict[str, JsonValue] = {}
        self._extensions: dict[str, JsonValue] = {}

    def add_content(self, content: MessageContent) -> Self:
        """Append one content value in producer-supplied order.

        Args:
            content: Standard or provider-defined structural content.

        Returns:
            This builder for fluent construction.

        Raises:
            TypeError: If ``content`` does not implement ``MessageContent``.
        """
        candidate = cast(object, content)
        # Check the open protocol before mutation so a failed call leaves the
        # builder usable and preserves all content already accumulated.
        if not isinstance(candidate, MessageContent):
            raise TypeError(
                "MessageEntryBuilder content must implement MessageContent."
            )
        self._content.append(candidate)
        return self

    def add_relation(self, relation: MessageRelation) -> Self:
        """Append one directed element relation in declaration order.

        Args:
            relation: Immutable relation to retain on the resulting entry.

        Returns:
            This builder for fluent construction.

        Raises:
            TypeError: If ``relation`` is not a ``MessageRelation``.
        """
        candidate = cast(object, relation)
        # Relations are nominal immutable values. Endpoint resolution remains a
        # document-level concern and is deliberately not duplicated here.
        if not isinstance(candidate, MessageRelation):
            raise TypeError("MessageEntryBuilder relation must be a MessageRelation.")
        self._relations.append(candidate)
        return self

    def with_metadata(self, metadata: Extensions) -> Self:
        """Replace descriptive metadata with an owned mapping snapshot.

        Args:
            metadata: String-keyed JSON metadata for the resulting entry.

        Returns:
            This builder for fluent construction.

        Raises:
            TypeError: If ``metadata`` is not a string-keyed mapping.
        """
        # Snapshot top-level membership at the fluent call boundary so later
        # caller mutations cannot silently change a future build result.
        self._metadata = _snapshot_mapping(metadata, "metadata")
        return self

    def with_extensions(self, extensions: Extensions) -> Self:
        """Replace unknown fields with an owned mapping snapshot.

        Args:
            extensions: String-keyed forward-compatible JSON fields.

        Returns:
            This builder for fluent construction.

        Raises:
            TypeError: If ``extensions`` is not a string-keyed mapping.
        """
        # Keep unknown fields separate from descriptive metadata and own their
        # membership independently to prevent cross-channel aliasing.
        self._extensions = _snapshot_mapping(extensions, "extensions")
        return self

    def build(self) -> MessageEntry:
        """Create and validate a new immutable message entry.

        Returns:
            A fresh ``MessageEntry`` equivalent to direct construction with the
            builder's current fields.

        Raises:
            TypeError: If a dynamically supplied field has an invalid shape.
            ValueError: If entry identity, role, content, or JSON semantics are
                invalid.
        """
        # Tuple conversion freezes current order for this result. MessageEntry
        # independently snapshots both mappings, so later builder calls cannot
        # mutate an entry that has already been returned.
        entry = MessageEntry(
            self._entry_id,
            self._role,
            tuple(self._content),
            relations=tuple(self._relations),
            metadata=self._metadata,
            extensions=self._extensions,
        )
        # Reuse the one semantic authority rather than reproducing role, content,
        # identifier, or recursive JSON rules inside the builder.
        return validate_message_entry(entry)


def _snapshot_mapping(value: Extensions, field_name: str) -> dict[str, JsonValue]:
    """Return an owned string-keyed mapping without interpreting JSON values."""
    candidate = cast(object, value)
    # Mapping supports custom read-only inputs, while string keys preserve the
    # language-neutral JSON object boundary used by the immutable value object.
    if not isinstance(candidate, Mapping):
        raise TypeError(f"MessageEntryBuilder {field_name} must be a mapping.")
    source = cast(Mapping[object, object], candidate)
    if any(not isinstance(key, str) for key in source):
        raise TypeError(f"MessageEntryBuilder {field_name} keys must be strings.")

    # Recursive JSON and number rules are intentionally deferred to build(),
    # where the existing MessageEntry validator remains the semantic authority.
    return dict(cast(Mapping[str, JsonValue], source))
