"""Catalog-local immutable value tests for ArtifactReference."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import FrozenInstanceError, fields
from typing import cast

from mconet.core.domain import ArtifactReference, Extensions, JsonValue, OpenIdentifier


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    # Keep execution inside a narrow try block so unexpected success or a wrong
    # exception type produces a direct, actionable test failure.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def _mutate_metadata(metadata: dict[str, JsonValue]) -> None:
    """Attempt item assignment after deliberately crossing the static boundary."""
    # Dynamic narrowing is isolated here so the test can prove the runtime view
    # rejects mutation in addition to the public Mapping type forbidding it.
    metadata["changed"] = True


def _serialize_reference(reference: ArtifactReference) -> dict[str, JsonValue]:
    """Serialize one reference using language-neutral public field names."""
    document: dict[str, JsonValue] = {
        "artifactId": reference.artifact_id,
        "metadata": dict(reference.metadata),
    }
    # Absence remains distinct from an invented relation value, while unknown
    # present identifiers are copied exactly without a known-relation registry.
    if reference.relation is not None:
        document["relation"] = reference.relation.value
    return document


def _require_object(value: JsonValue, field_name: str) -> dict[str, JsonValue]:
    """Return one required JSON object without coercing another value kind."""
    # Named object fields keep reference representations portable and prevent
    # positional or scalar alternatives from becoming platform-specific forms.
    if not isinstance(value, dict):
        raise AssertionError(f"{field_name} must be a JSON object.")
    return value


def _require_string(value: JsonValue | None, field_name: str) -> str:
    """Return one required JSON string without host-language conversion."""
    # IDs and relation identifiers retain exact text; null, numbers, booleans,
    # arrays, and objects are never converted into accidental reference values.
    if not isinstance(value, str):
        raise AssertionError(f"{field_name} must be a JSON string.")
    return value


def _deserialize_reference(document: dict[str, JsonValue]) -> ArtifactReference:
    """Reconstruct one reference from its portable JSON representation."""
    relation_value = document.get("relation")
    metadata = _require_object(document.get("metadata"), "metadata")

    # Construct a fresh open relation identifier without resolving the artifact;
    # the enclosing catalog remains the sole reference lookup scope.
    return ArtifactReference(
        artifact_id=_require_string(document.get("artifactId"), "artifactId"),
        relation=(
            OpenIdentifier(_require_string(relation_value, "relation"))
            if relation_value is not None
            else None
        ),
        metadata=metadata,
    )


def test_artifact_reference_preserves_local_id_relation_and_metadata() -> None:
    """Verify every descriptive field retains an independent public meaning."""
    relation = OpenIdentifier("artifact.preview_of")
    reference = ArtifactReference(
        artifact_id="image-preview",
        relation=relation,
        metadata={"page": 1, "preferred": True},
    )

    # The local ID is not rewritten as a URI or global identity, and optional
    # relation semantics do not replace per-reference metadata.
    assert reference.artifact_id == "image-preview"
    assert reference.relation is relation
    assert reference.metadata == {"page": 1, "preferred": True}
    assert _serialize_reference(reference) == {
        "artifactId": "image-preview",
        "relation": "artifact.preview_of",
        "metadata": {"page": 1, "preferred": True},
    }


def test_artifact_reference_preserves_unknown_relation_through_json() -> None:
    """Verify provider relation and metadata survive a real JSON round trip."""
    reference = ArtifactReference(
        artifact_id="provider-object-7",
        relation=OpenIdentifier("vendor.calibration_source"),
        metadata={"vendor.rank": 2},
    )

    # Encoding and decoding actual JSON proves preservation does not depend on
    # Python object identity or a registry of recognized relation identifiers.
    encoded = json.dumps(_serialize_reference(reference), sort_keys=True)
    decoded: JsonValue = json.loads(encoded)
    restored = _deserialize_reference(_require_object(decoded, "reference"))

    assert restored == reference
    assert restored.relation is not reference.relation
    assert restored.relation == OpenIdentifier("vendor.calibration_source")
    assert restored.metadata == {"vendor.rank": 2}


def test_artifact_reference_defaults_are_explicit_and_immutable() -> None:
    """Verify omitted optional data becomes None and an immutable empty mapping."""
    reference = ArtifactReference("artifact-1")

    # The optional relation is not replaced by a sentinel identifier, and empty
    # metadata remains an actual collection rather than null.
    assert reference.relation is None
    assert reference.metadata == {}
    assert _serialize_reference(reference) == {
        "artifactId": "artifact-1",
        "metadata": {},
    }


def test_artifact_reference_snapshots_metadata_and_is_immutable() -> None:
    """Verify caller changes and public assignments cannot alter a reference."""
    metadata: dict[str, JsonValue] = {"label": "original"}
    reference = ArtifactReference("artifact-1", metadata=metadata)

    # Construction owns top-level membership, while frozen fields and the proxy
    # reject changes through both object and mapping surfaces.
    metadata["label"] = "changed"
    assert reference.metadata == {"label": "original"}
    _assert_raises(
        FrozenInstanceError,
        lambda: reference.__setattr__("artifact_id", "other"),
        "cannot assign to field",
    )
    _assert_raises(
        TypeError,
        lambda: _mutate_metadata(cast(dict[str, JsonValue], reference.metadata)),
        "does not support item assignment",
    )


def test_artifact_reference_keeps_resolution_in_the_enclosing_catalog() -> None:
    """Verify construction retains an unresolved local ID without external scope."""
    reference = ArtifactReference("not-yet-indexed")

    # A standalone value has no catalog index, so it neither rejects a missing ID
    # nor searches another request, result, client, session, URI, or filesystem.
    assert reference.artifact_id == "not-yet-indexed"
    assert tuple(field.name for field in fields(ArtifactReference)) == (
        "artifact_id",
        "relation",
        "metadata",
    )


def test_artifact_reference_rejects_invalid_storage_shapes() -> None:
    """Verify dynamic callers cannot bypass field and mapping type contracts."""
    # Each field fails at its own storage boundary before a later resolver can
    # mistake malformed data for a valid but missing catalog-local reference.
    _assert_raises(
        TypeError,
        lambda: ArtifactReference(cast(str, 7)),
        "artifact_id must be a string",
    )
    _assert_raises(
        TypeError,
        lambda: ArtifactReference(
            "artifact-1", relation=cast(OpenIdentifier, "artifact.input")
        ),
        "relation must be an OpenIdentifier or None",
    )
    _assert_raises(
        TypeError,
        lambda: ArtifactReference("artifact-1", metadata=cast(Extensions, [])),
        "metadata must be a mapping",
    )
    _assert_raises(
        TypeError,
        lambda: ArtifactReference(
            "artifact-1", metadata=cast(Extensions, {1: "value"})
        ),
        "metadata keys must be strings",
    )


def test_artifact_reference_rejects_nonportable_metadata_values() -> None:
    """Verify metadata contains only recursive portable JSON values."""
    cyclic: list[JsonValue] = []
    cyclic.append(cyclic)

    # Structural and numeric checks exclude host objects, cycles, unsafe integers,
    # and non-finite numbers while leaving valid unknown metadata keys untouched.
    for metadata, exception_type, message in (
        ({"tuple": cast(JsonValue, ("not", "json"))}, TypeError, "JsonValue"),
        ({"cycle": cyclic}, TypeError, "JsonValue"),
        ({"large": 2**53}, ValueError, "safe range"),
        ({"nan": float("nan")}, ValueError, "finite"),
    ):
        _assert_raises(
            exception_type,
            lambda metadata=metadata: ArtifactReference(
                "artifact-1", metadata=metadata
            ),
            message,
        )
