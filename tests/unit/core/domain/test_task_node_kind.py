"""Open structural contract tests for TaskNodeKind implementations."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal, cast

from mconet.core.domain import (
    JsonValue,
    MessageElementKind,
    OpenIdentifier,
    TaskNodeKind,
)


@dataclass(frozen=True, slots=True)
class _Kind:
    """Immutable custom kind proving structural implementation without inheritance."""

    id: OpenIdentifier
    """Standard or provider-defined task node kind identifier."""

    composition: Literal["leaf", "container"]
    """Declared task tree composition mode."""


def _serialize_kind(kind: TaskNodeKind) -> dict[str, JsonValue]:
    """Serialize one task kind into its language-neutral public field shape."""
    # Both fields are required and copied independently; identifier parsing is
    # never used to derive or normalize structural composition.
    return {
        "id": kind.id.value,
        "composition": kind.composition,
    }


def _require_object(value: JsonValue, field_name: str) -> dict[str, JsonValue]:
    """Return one required object-valued decoded task kind document."""
    # Requiring an object root prevents positional or scalar representations from
    # becoming language-specific alternatives to the named public fields.
    if not isinstance(value, dict):
        raise AssertionError(f"{field_name} must be a JSON object.")
    return value


def _require_string(value: JsonValue | None, field_name: str) -> str:
    """Return one required string-valued decoded task kind field."""
    # Host-language coercion is forbidden so identifiers preserve exact producer
    # text instead of accepting a value that was not a JSON string.
    if not isinstance(value, str):
        raise AssertionError(f"{field_name} must be a JSON string.")
    return value


def _require_composition(
    value: JsonValue | None,
) -> Literal["leaf", "container"]:
    """Return one decoded composition after checking the two-value contract."""
    # Runtime decoding must narrow ordinary JSON text before constructing the
    # statically typed custom protocol implementation.
    if isinstance(value, str) and value in ("leaf", "container"):
        return value
    raise AssertionError("composition must be leaf or container.")


def _deserialize_kind(document: dict[str, JsonValue]) -> _Kind:
    """Reconstruct one custom task kind from its portable field shape."""
    # Each field uses its explicit boundary so an unknown ID remains exact rather
    # than being mapped through a closed standard-kind registry.
    return _Kind(
        id=OpenIdentifier(_require_string(document.get("id"), "id")),
        composition=_require_composition(document.get("composition")),
    )


def _accept_task_kind(kind: TaskNodeKind) -> tuple[OpenIdentifier, str]:
    """Expose the protocol fields through a statically checked consumer."""
    # Reading only the public protocol surface proves custom implementations need
    # no SDK inheritance or additional message-domain classification field.
    return kind.id, kind.composition


def test_task_node_kind_expresses_identity_and_composition_independently() -> None:
    """Verify standard leaf and container kinds retain independent facts."""
    task_input = _Kind(id=OpenIdentifier("task.input"), composition="leaf")
    task_root = _Kind(id=OpenIdentifier("task.root"), composition="container")

    # Structural conformance does not require inheritance, and composition is an
    # explicit value rather than a convention inferred from an identifier suffix.
    assert isinstance(task_input, TaskNodeKind)
    assert isinstance(task_root, TaskNodeKind)
    assert _accept_task_kind(task_input) == (
        OpenIdentifier("task.input"),
        "leaf",
    )
    assert _serialize_kind(task_input) == {
        "id": "task.input",
        "composition": "leaf",
    }
    assert _serialize_kind(task_root) == {
        "id": "task.root",
        "composition": "container",
    }


def test_task_node_kind_preserves_unknown_kind_through_json() -> None:
    """Verify an unknown identity and its composition survive a JSON round trip."""
    kind = _Kind(
        id=OpenIdentifier("vendor.review_plan"),
        composition="container",
    )

    # Encoding and decoding actual JSON proves equality does not depend on Python
    # object identity or a registry of recognized task node identifiers.
    encoded = json.dumps(_serialize_kind(kind), sort_keys=True)
    decoded: JsonValue = json.loads(encoded)
    restored = _deserialize_kind(_require_object(decoded, "kind"))

    assert isinstance(restored, TaskNodeKind)
    assert restored == kind
    assert restored.id is not kind.id
    assert _serialize_kind(restored) == _serialize_kind(kind)


def test_task_node_kind_requires_complete_task_specific_surface() -> None:
    """Verify identity alone is incomplete and task kinds remain message-neutral."""

    @dataclass(frozen=True, slots=True)
    class _IncompleteKind:
        """Intentionally omit the task tree composition property."""

        id: OpenIdentifier
        """Kind identity without structural classification is incomplete."""

    incomplete = _IncompleteKind(OpenIdentifier("task.input"))
    complete = _Kind(OpenIdentifier("task.input"), "leaf")

    # Runtime protocol membership requires both task fields. A complete task kind
    # deliberately lacks MessageElementKind.category, keeping both domains apart.
    assert not isinstance(incomplete, TaskNodeKind)
    assert not isinstance(cast(object, OpenIdentifier("task.input")), TaskNodeKind)
    assert isinstance(complete, TaskNodeKind)
    assert not isinstance(complete, MessageElementKind)
