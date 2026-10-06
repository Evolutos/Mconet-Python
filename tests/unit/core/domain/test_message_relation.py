"""Directed-reference contract tests for immutable MessageRelation values."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import FrozenInstanceError
from typing import cast

from mconet.core.domain import Extensions, JsonValue, MessageRelation, OpenIdentifier


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    # Execute inside a narrow try block so an unexpected success or exception
    # type produces a direct test failure instead of hiding the invalid branch.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def _mutate_metadata(metadata: dict[str, JsonValue]) -> None:
    """Attempt one item assignment through a dynamically narrowed mapping."""
    # This helper crosses the static read-only boundary deliberately so the test
    # can prove the runtime mapping also rejects mutation.
    metadata["changed"] = True


def _serialize_relation(relation: MessageRelation) -> dict[str, JsonValue]:
    """Serialize one relation using its language-neutral public field names."""
    # Source and target remain separate fields to preserve direction; relation
    # type stays an open identifier and metadata is copied into a JSON object.
    return {
        "source": relation.source,
        "target": relation.target,
        "type": relation.type.value,
        "metadata": dict(relation.metadata),
    }


def _require_object(value: JsonValue, field_name: str) -> dict[str, JsonValue]:
    """Return one required JSON object without coercing another value kind."""
    # Exact object recognition avoids inventing positional relation formats and
    # keeps malformed scalar or array documents outside the field contract.
    if not isinstance(value, dict):
        raise AssertionError(f"{field_name} must be a JSON object.")
    return value


def _require_string(value: JsonValue | None, field_name: str) -> str:
    """Return one required JSON string without host-language conversion."""
    # Reject null, booleans, numbers, and containers instead of converting them
    # into endpoint or type text that was never present in the wire document.
    if not isinstance(value, str):
        raise AssertionError(f"{field_name} must be a JSON string.")
    return value


def _deserialize_relation(document: dict[str, JsonValue]) -> MessageRelation:
    """Reconstruct one relation from its public JSON field representation."""
    metadata = _require_object(document.get("metadata"), "metadata")
    # Construct a fresh open identifier without a known-type lookup so future
    # relation namespaces and metadata remain available to older consumers.
    return MessageRelation(
        source=_require_string(document.get("source"), "source"),
        target=_require_string(document.get("target"), "target"),
        type=OpenIdentifier(_require_string(document.get("type"), "type")),
        metadata=metadata,
    )


def test_message_relation_preserves_directed_reference_semantics() -> None:
    """Verify source, target, type, and metadata retain independent meanings."""
    relation_type = OpenIdentifier("message.cites")
    relation = MessageRelation(
        source="answer",
        target="citation-1",
        type=relation_type,
        metadata={"confidence": 0.9, "required": True},
    )

    # Direction is never inferred from ordering or metadata: each endpoint and
    # the exact open relation type remains independently observable.
    assert relation.source == "answer"
    assert relation.target == "citation-1"
    assert relation.type is relation_type
    assert relation.metadata == {"confidence": 0.9, "required": True}
    assert _serialize_relation(relation) == {
        "source": "answer",
        "target": "citation-1",
        "type": "message.cites",
        "metadata": {"confidence": 0.9, "required": True},
    }


def test_message_relation_preserves_unknown_type_through_json() -> None:
    """Verify an unknown relation type and metadata survive a real JSON round trip."""
    relation = MessageRelation(
        source="provider-node",
        target="entry",
        type=OpenIdentifier("vendor.supports"),
        metadata={"providerData": {"rank": 2}},
    )

    # Encoding and decoding through JSON proves preservation does not depend on
    # Python object identity or a registry of recognized relation identifiers.
    encoded = json.dumps(_serialize_relation(relation), sort_keys=True)
    decoded: JsonValue = json.loads(encoded)
    restored = _deserialize_relation(_require_object(decoded, "relation"))

    assert restored == relation
    assert restored.type is not relation.type
    assert restored.type.value == "vendor.supports"
    assert restored.metadata == {"providerData": {"rank": 2}}


def test_message_relation_snapshots_metadata_and_is_immutable() -> None:
    """Verify caller membership changes and assignments cannot alter a relation."""
    metadata: dict[str, JsonValue] = {"label": "original"}
    relation = MessageRelation(
        "source", "target", OpenIdentifier("message.links"), metadata
    )

    # The constructor owns a top-level snapshot, while frozen fields and the
    # read-only proxy prevent mutation through either public storage surface.
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


def test_message_relation_does_not_resolve_document_local_endpoints() -> None:
    """Verify construction preserves unresolved endpoint IDs for document validation."""
    relation = MessageRelation("missing", "missing", OpenIdentifier("vendor.self"))

    # A relation lacks the enclosing element index, so it retains even equal or
    # unresolved IDs; the later document validator decides whether they exist.
    assert relation.source == "missing"
    assert relation.target == "missing"
    assert relation.metadata == {}


def test_message_relation_rejects_invalid_storage_shapes() -> None:
    """Verify dynamic callers cannot bypass endpoint, type, or metadata contracts."""
    relation_type = OpenIdentifier("message.links")

    # Each field fails at its own boundary so invalid input cannot be mistaken
    # for a missing document endpoint during later reference validation.
    _assert_raises(
        TypeError,
        lambda: MessageRelation(cast(str, 1), "target", relation_type),
        "source must be a string",
    )
    _assert_raises(
        TypeError,
        lambda: MessageRelation("source", cast(str, 1), relation_type),
        "target must be a string",
    )
    _assert_raises(
        TypeError,
        lambda: MessageRelation(
            "source", "target", cast(OpenIdentifier, "message.links")
        ),
        "type must be an OpenIdentifier",
    )
    _assert_raises(
        TypeError,
        lambda: MessageRelation(
            "source", "target", relation_type, cast(Extensions, [])
        ),
        "metadata must be a mapping",
    )
    _assert_raises(
        TypeError,
        lambda: MessageRelation(
            "source",
            "target",
            relation_type,
            cast(Extensions, {1: "value"}),
        ),
        "metadata keys must be strings",
    )


def test_message_relation_rejects_nonportable_metadata_values() -> None:
    """Verify metadata contains only recursive portable JSON values."""
    relation_type = OpenIdentifier("message.links")
    cyclic: list[JsonValue] = []
    cyclic.append(cyclic)

    # Structural and numeric checks prevent invalid data from reaching schema
    # serialization while leaving valid unknown metadata keys untouched.
    for metadata, exception_type, message in (
        ({"tuple": cast(JsonValue, ("not", "json"))}, TypeError, "JsonValue"),
        ({"cycle": cyclic}, TypeError, "JsonValue"),
        ({"large": 2**53}, ValueError, "safe range"),
        ({"nan": float("nan")}, ValueError, "finite"),
    ):
        _assert_raises(
            exception_type,
            lambda metadata=metadata: MessageRelation(
                "source", "target", relation_type, metadata
            ),
            message,
        )
