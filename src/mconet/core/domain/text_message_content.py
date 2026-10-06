"""Immutable text content for message entry content collections."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType, SimpleNamespace
from typing import cast

from mconet.core.domain.extensions import Extensions
from mconet.core.domain.json_value import JsonValue
from mconet.core.domain.message_content_kind import MessageContentKind
from mconet.core.domain.open_identifier import OpenIdentifier

_EMPTY_EXTENSIONS: Extensions = MappingProxyType({})
_TEXT_CONTENT_KIND_ID = OpenIdentifier("content.text")


def _empty_extensions() -> Extensions:
    """Return the shared immutable empty mapping used by content defaults."""
    # The mapping contains no nested values and cannot be mutated, so sharing it
    # avoids allocations without introducing shared writable state.
    return _EMPTY_EXTENSIONS


def _text_content_kind() -> MessageContentKind:
    """Return an isolated structural view of the fixed text content kind."""
    # SimpleNamespace supplies the protocol's single attribute without defining
    # a second production type. A fresh view prevents dynamic callers from
    # changing the kind returned by later property reads.
    view = SimpleNamespace(id=_TEXT_CONTENT_KIND_ID)
    return cast(MessageContentKind, view)


@dataclass(frozen=True, slots=True)
class TextMessageContent:
    """Carry one text payload independently from message elements and tasks.

    The content kind is always ``content.text`` and is not a constructor input.
    Text is preserved exactly; Unicode semantics, length policy, and other text
    validation remain responsibilities of the dedicated validator. Metadata and
    extension mappings are copied and exposed through read-only views.
    """

    id: str
    """Stable content identifier local to the enclosing message document."""

    text: str
    """Exact text payload without trimming or normalization."""

    metadata: Extensions = field(default_factory=_empty_extensions)
    """Read-only non-control metadata snapshot."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Read-only unknown-field snapshot for forward compatibility."""

    def __post_init__(self) -> None:
        """Require primitive storage types and freeze mapping membership."""
        content_id = cast(object, self.id)
        text = cast(object, self.text)

        # Construction enforces only storage shape. Non-empty ID rules, text
        # length, and Unicode policy belong to later validation work.
        if not isinstance(content_id, str):
            raise TypeError("TextMessageContent id must be a string.")
        if not isinstance(text, str):
            raise TypeError("TextMessageContent text must be a string.")

        # Copy top-level membership so caller mutations cannot change the
        # immutable content after construction; JSON validation stays separate.
        object.__setattr__(
            self, "metadata", _snapshot_mapping(self.metadata, "metadata")
        )
        object.__setattr__(
            self,
            "extensions",
            _snapshot_mapping(self.extensions, "extensions"),
        )

    @property
    def kind(self) -> MessageContentKind:
        """Return the fixed ``content.text`` representation kind."""
        # Constructing an isolated structural view keeps the public kind fixed
        # even if dynamic code mutates a previously returned namespace object.
        return _text_content_kind()


def _snapshot_mapping(value: Extensions, field_name: str) -> Extensions:
    """Copy one string-keyed mapping and expose read-only membership."""
    candidate = cast(object, value)
    # Mapping accepts custom read-only implementations while rejecting sequences
    # and other containers that cannot represent JSON object membership.
    if not isinstance(candidate, Mapping):
        raise TypeError(f"TextMessageContent {field_name} must be a mapping.")
    source = cast(Mapping[object, object], candidate)
    if any(not isinstance(key, str) for key in source):
        raise TypeError(f"TextMessageContent {field_name} keys must be strings.")

    # Preserve values exactly and defer recursive JSON/number rules to the text
    # content validator while detaching membership from the caller's mapping.
    snapshot = dict(cast(Mapping[str, JsonValue], source))
    return MappingProxyType(snapshot)
