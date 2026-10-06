"""Conformance checks for the independently loadable Artifact schema."""

import json
from pathlib import Path

from mconet.core.domain import JsonValue, OpenIdentifier
from mconet.testing import (
    SchemaLoader,
    SchemaValidationIssue,
    SchemaValidatorAdapter,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SCHEMA_PATH = _PROJECT_ROOT / "spec" / "schemas" / "artifact.json"
_SCHEMA_INDEX_PATH = _PROJECT_ROOT / "spec" / "schemas" / "index.json"
_SCHEMA_ID = OpenIdentifier("schema.artifact")
_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"


def _load_object(path: Path) -> dict[str, JsonValue]:
    """Load one committed UTF-8 JSON object document."""
    # Requiring an object root prevents an unrelated scalar or array resource
    # from entering the stable schema loader under the Artifact identifier.
    document: JsonValue = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise AssertionError(f"Expected a JSON object in {path}.")
    return document


def _adapter() -> SchemaValidatorAdapter:
    """Load the committed Artifact schema through the public toolchain."""
    # Identity and dialect are checked before registration so lookup cannot hide
    # drift in the independently distributed schema resource itself.
    schema = _load_object(_SCHEMA_PATH)
    assert schema.get("$id") == _SCHEMA_ID.value
    assert schema.get("$schema") == _SCHEMA_DIALECT
    return SchemaValidatorAdapter(SchemaLoader({_SCHEMA_ID: schema}))


def _artifact(source: dict[str, JsonValue]) -> dict[str, JsonValue]:
    """Create a minimal serialized Artifact around one selected source."""
    # A fresh document keeps source scenarios independent while using the same
    # required identity and open semantic Kind boundary in every assertion.
    return {
        "id": "artifact-1",
        "kind": {"id": "artifact.file"},
        "source": source,
    }


def test_artifact_schema_is_registered_and_domain_scoped() -> None:
    """Verify stable discovery and the exact shared Artifact field boundary."""
    schema = _load_object(_SCHEMA_PATH)
    index = _load_object(_SCHEMA_INDEX_PATH)
    properties = schema.get("properties")
    resources = index.get("resources")
    if not isinstance(properties, dict) or not isinstance(resources, list):
        raise AssertionError(
            "Schema properties or index resources have invalid shapes."
        )

    # Only shared descriptive fields belong at the Artifact root. Catalog,
    # reference, task, access, protocol, and content-operation concerns remain
    # separate contracts and cannot be smuggled into this schema.
    assert "artifact.json" in resources
    assert frozenset(properties) == frozenset(
        ("descriptor", "extensions", "id", "kind", "mediaType", "metadata", "source")
    )
    for unrelated_name in (
        "artifacts",
        "artifactId",
        "authorization",
        "endpoint",
        "read",
        "relation",
        "task",
        "upload",
    ):
        assert unrelated_name not in properties


def test_artifact_schema_accepts_minimal_and_complete_open_artifacts() -> None:
    """Verify optional absence and open Kind, Source, and Descriptor data."""
    adapter = _adapter()
    minimal: JsonValue = _artifact(
        {"kind": "vendor.memory_handle", "handleId": "opaque-1"}
    )
    complete: JsonValue = {
        "id": "depth-map-1",
        "kind": {
            "id": "vendor.depth_map",
            "semantic": "Depth values aligned to an image plane.",
            "extensions": {"vendor.version": 1},
        },
        "mediaType": "application/vnd.vendor.depth+binary; version=1",
        "source": {
            "kind": "vendor.object_store",
            "storeId": "store-a",
            "objectKey": "depth/1",
            "extensions": {"vendor.region": "east"},
        },
        "descriptor": {
            "kind": "vendor.spatial_grid",
            "dimensions": 3,
            "shape": [640, 480],
        },
        "metadata": {"calibrated": True},
        "extensions": {"vendor.trace": {"enabled": True}},
    }
    explicit_absence: JsonValue = {
        **_artifact({"kind": "vendor.opaque"}),
        "descriptor": None,
        "mediaType": None,
    }
    quoted_media_type: JsonValue = {
        **_artifact({"kind": "vendor.opaque"}),
        "mediaType": 'application/example; label="value with space"',
    }

    # Open identifiers and JSON-only provider facts survive without requiring a
    # central registry. Optional values distinguish null from omission, and media
    # parameters retain both token and quoted-string representations.
    assert adapter.validate(_SCHEMA_ID, minimal) == ()
    assert adapter.validate(_SCHEMA_ID, complete) == ()
    assert adapter.validate(_SCHEMA_ID, explicit_absence) == ()
    assert adapter.validate(_SCHEMA_ID, quoted_media_type) == ()


def test_artifact_schema_accepts_each_safe_concrete_source_shape() -> None:
    """Verify inline, URI, and path sources have portable representations."""
    adapter = _adapter()
    documents: tuple[JsonValue, ...] = (
        _artifact({"kind": "artifact.inline", "bytes": ""}),
        _artifact({"kind": "artifact.inline", "bytes": "007fff"}),
        _artifact(
            {
                "kind": "artifact.uri",
                "uri": {
                    "value": "https://content.example.test/a%2Fb",
                    "isAbsolute": True,
                },
            }
        ),
        _artifact(
            {
                "kind": "artifact.uri",
                "uri": {"value": "../content/item.bin", "isAbsolute": False},
            }
        ),
        _artifact({"kind": "artifact.local_file", "path": "../content/item.bin"}),
    )

    # Bytes use canonical lowercase hexadecimal text, URI retains its declared
    # form, and a local path stays lexical; validation performs no source I/O.
    for document in documents:
        assert adapter.validate(_SCHEMA_ID, document) == ()


def test_artifact_schema_rejects_root_contract_violations_stably() -> None:
    """Verify required fields, identities, media shape, and scope are enforced."""
    adapter = _adapter()
    invalid_documents: tuple[
        tuple[JsonValue, tuple[SchemaValidationIssue, ...]], ...
    ] = (
        (
            {"id": "artifact-1", "kind": {"id": "artifact.file"}},
            (
                SchemaValidationIssue(
                    "/source", "required", "Required property is missing."
                ),
            ),
        ),
        (
            _artifact({"kind": "vendor.memory"}) | {"id": "   "},
            (
                SchemaValidationIssue(
                    "/id", "pattern", "String does not match pattern."
                ),
            ),
        ),
        (
            {
                "id": "artifact-1",
                "kind": {"id": "Vendor.Invalid"},
                "source": {"kind": "vendor.memory"},
            },
            (
                SchemaValidationIssue(
                    "/kind/id", "pattern", "String does not match pattern."
                ),
            ),
        ),
        (
            _artifact({"kind": "vendor.memory"}) | {"mediaType": "text"},
            (
                SchemaValidationIssue(
                    "/mediaType",
                    "oneOf",
                    "Value must match exactly one schema alternative.",
                ),
            ),
        ),
        (
            _artifact({"kind": "vendor.memory"}) | {"mediaType": "text/plain;"},
            (
                SchemaValidationIssue(
                    "/mediaType",
                    "oneOf",
                    "Value must match exactly one schema alternative.",
                ),
            ),
        ),
        (
            _artifact({"kind": "vendor.memory"}) | {"task": {}},
            (
                SchemaValidationIssue(
                    "/task",
                    "additionalProperties",
                    "Additional property is not allowed.",
                ),
            ),
        ),
    )

    # Exact issue tuples freeze portable paths and keep unrelated request state
    # outside the independently validated Artifact object.
    for document, expected in invalid_documents:
        assert adapter.validate(_SCHEMA_ID, document) == expected


def test_artifact_schema_rejects_unsafe_or_malformed_source_shapes() -> None:
    """Verify known source kinds cannot fall through to the open-source branch."""
    adapter = _adapter()
    invalid_sources: tuple[dict[str, JsonValue], ...] = (
        {"kind": "artifact.inline", "bytes": "0"},
        {"kind": "artifact.inline", "bytes": "00FF"},
        {"kind": "artifact.inline"},
        {
            "kind": "artifact.uri",
            "uri": {"value": "https://example.test/content", "isAbsolute": True},
            "authorization": {"token": "not-serializable"},
        },
        {
            "kind": "artifact.uri",
            "uri": {"value": "https://example.test/content"},
        },
        {"kind": "artifact.local_file"},
        {"kind": "artifact.local_file", "fileHandle": "opaque-runtime-handle"},
    )
    expected = (
        SchemaValidationIssue(
            "/source",
            "oneOf",
            "Value must match exactly one schema alternative.",
        ),
    )

    # Concrete identifiers are excluded from the generic branch, so missing or
    # malformed data fails instead of being accepted as an unknown source. The
    # ordinary schema also cannot carry credentials or runtime file handles.
    for source in invalid_sources:
        assert adapter.validate(_SCHEMA_ID, _artifact(source)) == expected
