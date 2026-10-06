"""Directed-reference contract tests for immutable TaskRelation values."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import FrozenInstanceError, fields
from typing import cast

from mconet.core.domain import Extensions, JsonValue, OpenIdentifier, TaskRelation


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    # A narrow execution boundary prevents an unrelated setup failure from
    # satisfying the expected relation field or metadata diagnostic.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def _mutate_metadata(metadata: dict[str, JsonValue]) -> None:
    """Attempt item assignment through a deliberately narrowed mapping."""
    # Crossing the static read-only boundary proves the runtime proxy also rejects
    # mutation instead of relying only on the public Mapping annotation.
    metadata["changed"] = True


def _serialize_relation(relation: TaskRelation) -> dict[str, JsonValue]:
    """Serialize one relation using language-neutral public field names."""
    # Explicit source and target preserve direction, while type remains open and
    # metadata is copied as data without resolving either endpoint.
    return {
        "source": relation.source,
        "target": relation.target,
        "type": relation.type.value,
        "metadata": dict(relation.metadata),
    }


def _require_object(value: JsonValue, field_name: str) -> dict[str, JsonValue]:
    """Return one required JSON object without coercing another value kind."""
    # Named fields keep the portable relation representation unambiguous and
    # reject scalar or positional alternatives before reconstruction.
    if not isinstance(value, dict):
        raise AssertionError(f"{field_name} must be a JSON object.")
    return value


def _require_string(value: JsonValue | None, field_name: str) -> str:
    """Return one required JSON string without host-language conversion."""
    # Null, booleans, numbers, arrays, and objects cannot be stringified into
    # endpoint or relation-type values that were never present in the document.
    if not isinstance(value, str):
        raise AssertionError(f"{field_name} must be a JSON string.")
    return value


def _deserialize_relation(document: dict[str, JsonValue]) -> TaskRelation:
    """Reconstruct one task relation from its public JSON field shape."""
    metadata = _require_object(document.get("metadata"), "metadata")
    # A fresh identifier retains unknown namespaces without a known relation-type
    # registry, and construction deliberately leaves endpoint resolution pending.
    return TaskRelation(
        source=_require_string(document.get("source"), "source"),
        target=_require_string(document.get("target"), "target"),
        type=OpenIdentifier(_require_string(document.get("type"), "type")),
        metadata=metadata,
    )


def test_task_relation_preserves_directed_reference_semantics() -> None:
    """Verify source, target, type, and metadata retain independent meanings."""
    relation_type = OpenIdentifier("task.depends_on")
    relation = TaskRelation(
        source="generation",
        target="input",
        type=relation_type,
        metadata={"priority": 1, "required": True},
    )

    # Direction is never inferred from storage order or metadata; each endpoint
    # and the exact open semantic identifier remain independently observable.
    assert relation.source == "generation"
    assert relation.target == "input"
    assert relation.type is relation_type
    assert relation.metadata == {"priority": 1, "required": True}
    assert _serialize_relation(relation) == {
        "source": "generation",
        "target": "input",
        "type": "task.depends_on",
        "metadata": {"priority": 1, "required": True},
    }


def test_task_relation_preserves_unknown_type_through_json() -> None:
    """Verify provider relation semantics survive a complete JSON round trip."""
    relation = TaskRelation(
        source="provider-step",
        target="input",
        type=OpenIdentifier("vendor.calibrates"),
        metadata={"vendor.rank": 2},
    )

    # Encoding and decoding actual JSON proves fidelity does not depend on Python
    # object identity or a closed registry of recognized relation identifiers.
    encoded = json.dumps(_serialize_relation(relation), sort_keys=True)
    decoded: JsonValue = json.loads(encoded)
    restored = _deserialize_relation(_require_object(decoded, "relation"))

    assert restored == relation
    assert restored.type is not relation.type
    assert restored.type == OpenIdentifier("vendor.calibrates")
    assert restored.metadata == {"vendor.rank": 2}


def test_task_relation_defaults_are_explicit_and_domain_specific() -> None:
    """Verify empty metadata and field names form the complete task relation."""
    relation = TaskRelation("source", "target", OpenIdentifier("task.links"))

    # An explicit empty mapping avoids null ambiguity. Exact fields also prove the
    # value carries no message, artifact, task payload, or traversal state.
    assert relation.metadata == {}
    assert tuple(field.name for field in fields(TaskRelation)) == (
        "source",
        "target",
        "type",
        "metadata",
    )


def test_task_relation_snapshots_metadata_and_is_immutable() -> None:
    """Verify caller membership changes and assignments cannot alter a relation."""
    metadata: dict[str, JsonValue] = {"label": "original"}
    relation = TaskRelation("source", "target", OpenIdentifier("task.links"), metadata)

    # Construction owns top-level mapping membership; frozen fields and the
    # read-only proxy reject mutation through both public storage surfaces.
    metadata["label"] = "changed"
    assert relation.metadata == {"label": "original"}
    _assert_raises(
        FrozenInstanceError,
        lambda: relation.__setattr__("target", "other"),
        "cannot assign to field",
    )
    _assert_raises(
        TypeError,
        lambda: _mutate_metadata(cast(dict[str, JsonValue], relation.metadata)),
        "does not support item assignment",
    )


def test_task_relation_defers_document_local_resolution() -> None:
    """Verify construction preserves unresolved and self-referencing endpoint IDs."""
    relation = TaskRelation("missing", "missing", OpenIdentifier("vendor.self"))

    # A standalone relation has no enclosing node index, so equal or absent IDs
    # remain data for later TaskDocument graph validation rather than failing here.
    assert relation.source == "missing"
    assert relation.target == "missing"
    assert relation.metadata == {}


def test_task_relation_rejects_invalid_storage_shapes() -> None:
    """Verify dynamic callers cannot bypass endpoint, type, or mapping contracts."""
    relation_type = OpenIdentifier("task.links")

    # Every malformed field fails at its own construction boundary before later
    # graph validation could misclassify it as a missing node reference.
    _assert_raises(
        TypeError,
        lambda: TaskRelation(cast(str, 1), "target", relation_type),
        "source must be a string",
    )
    _assert_raises(
        TypeError,
        lambda: TaskRelation("source", cast(str, 1), relation_type),
        "target must be a string",
    )
    _assert_raises(
        TypeError,
        lambda: TaskRelation("source", "target", cast(OpenIdentifier, "task.links")),
        "type must be an OpenIdentifier",
    )
    _assert_raises(
        TypeError,
        lambda: TaskRelation("source", "target", relation_type, cast(Extensions, [])),
        "metadata must be a mapping",
    )
    _assert_raises(
        TypeError,
        lambda: TaskRelation(
            "source",
            "target",
            relation_type,
            cast(Extensions, {1: "value"}),
        ),
        "metadata keys must be strings",
    )


def test_task_relation_rejects_nonportable_metadata_values() -> None:
    """Verify metadata contains only recursive portable JSON values."""
    relation_type = OpenIdentifier("task.links")
    cyclic: list[JsonValue] = []
    cyclic.append(cyclic)

    # Structural and numeric checks exclude host objects, cycles, unsafe integers,
    # and non-finite values while leaving valid unknown metadata keys untouched.
    for metadata, exception_type, message in (
        ({"tuple": cast(JsonValue, ("not", "json"))}, TypeError, "JsonValue"),
        ({"cycle": cyclic}, TypeError, "JsonValue"),
        ({"large": 2**53}, ValueError, "safe range"),
        ({"nan": float("nan")}, ValueError, "finite"),
    ):
        _assert_raises(
            exception_type,
            lambda metadata=metadata: TaskRelation(
                "source", "target", relation_type, metadata
            ),
            message,
        )
