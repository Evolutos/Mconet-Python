"""Open structural contract tests for MessageElementKind implementations."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal, cast

from mconet.core.domain import JsonValue, MessageElementKind, OpenIdentifier


@dataclass(frozen=True, slots=True)
class _Kind:
    """Immutable custom kind proving structural implementation without inheritance."""

    id: OpenIdentifier
    """Standard or provider-defined kind identifier."""

    category: str
    """Exact producer-defined category text."""

    composition: Literal["leaf", "container"]
    """Declared message tree composition mode."""


def _serialize_kind(kind: MessageElementKind) -> dict[str, JsonValue]:
    """Serialize one kind into its language-neutral public field shape."""
    # All three fields are required and copied independently; no identifier
    # parsing is used to derive or normalize category or composition.
    return {
        "id": kind.id.value,
        "category": kind.category,
        "composition": kind.composition,
    }


def _require_object(value: JsonValue, field_name: str) -> dict[str, JsonValue]:
    """Return one required object-valued decoded kind document."""
    # Requiring an object root prevents positional or scalar representations from
    # becoming language-specific alternatives to the named public fields.
    if not isinstance(value, dict):
        raise AssertionError(f"{field_name} must be a JSON object.")
    return value


def _require_string(value: JsonValue | None, field_name: str) -> str:
    """Return one required string-valued decoded kind field."""
    # Host-language coercion is forbidden so identifiers and categories preserve
    # exact producer text across the JSON boundary.
    if not isinstance(value, str):
        raise AssertionError(f"{field_name} must be a JSON string.")
    return value


def _require_composition(
    value: JsonValue | None,
) -> Literal["leaf", "container"]:
    """Return one decoded composition after checking the two-value contract."""
    # Runtime decoding must narrow ordinary JSON text before constructing the
    # statically typed custom implementation.
    if isinstance(value, str) and value in ("leaf", "container"):
        return value
    raise AssertionError("composition must be leaf or container.")


def _deserialize_kind(document: dict[str, JsonValue]) -> _Kind:
    """Reconstruct one custom kind from its language-neutral field shape."""
    # Each field uses its explicit value boundary; unknown IDs and categories
    # remain exact rather than being mapped through a standard-kind registry.
    return _Kind(
        id=OpenIdentifier(_require_string(document.get("id"), "id")),
        category=_require_string(document.get("category"), "category"),
        composition=_require_composition(document.get("composition")),
    )


def test_message_element_kind_expresses_category_and_composition_independently() -> (
    None
):
    """Verify standard leaf and container kinds retain all independent facts."""
    entry = _Kind(
        id=OpenIdentifier("message.entry"),
        category="entry",
        composition="leaf",
    )
    history = _Kind(
        id=OpenIdentifier("message.history"),
        category="group",
        composition="container",
    )

    # Structural conformance does not require inheritance, and differing
    # composition does not force category to be derived from identifier text.
    assert isinstance(entry, MessageElementKind)
    assert isinstance(history, MessageElementKind)
    assert _serialize_kind(entry) == {
        "id": "message.entry",
        "category": "entry",
        "composition": "leaf",
    }
    assert _serialize_kind(history) == {
        "id": "message.history",
        "category": "group",
        "composition": "container",
    }


def test_message_element_kind_preserves_unknown_kind_through_json() -> None:
    """Verify unknown identity and category survive a full JSON round trip."""
    kind = _Kind(
        id=OpenIdentifier("vendor.review_block"),
        category="vendor.review",
        composition="container",
    )

    # Encode and decode actual JSON so equality cannot be satisfied merely by
    # reusing the original Python object or its OpenIdentifier reference.
    encoded = json.dumps(_serialize_kind(kind), sort_keys=True)
    decoded: JsonValue = json.loads(encoded)
    restored = _deserialize_kind(_require_object(decoded, "kind"))

    assert isinstance(restored, MessageElementKind)
    assert restored == kind
    assert restored.id is not kind.id
    assert _serialize_kind(restored) == _serialize_kind(kind)


def test_message_element_kind_requires_complete_structural_surface() -> None:
    """Verify identity alone cannot satisfy category and composition semantics."""

    @dataclass(frozen=True, slots=True)
    class _IncompleteKind:
        """Intentionally omit category and composition properties."""

        id: OpenIdentifier
        """Kind identity without structural classification is incomplete."""

    incomplete = _IncompleteKind(OpenIdentifier("message.entry"))

    # Runtime Protocol membership requires all three properties so later element
    # logic never needs implementation-specific reflection for missing fields.
    assert not isinstance(incomplete, MessageElementKind)
    assert not isinstance(
        cast(object, OpenIdentifier("message.entry")), MessageElementKind
    )
