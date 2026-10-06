"""Conformance checks for the self-contained ArtifactCatalog schema."""

import json
from pathlib import Path

from mconet.core.domain import JsonValue, OpenIdentifier
from mconet.testing import (
    SchemaLoader,
    SchemaValidationIssue,
    SchemaValidatorAdapter,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SCHEMA_ROOT = _PROJECT_ROOT / "spec" / "schemas"
_CATALOG_SCHEMA_PATH = _SCHEMA_ROOT / "artifact-catalog.json"
_ARTIFACT_SCHEMA_PATH = _SCHEMA_ROOT / "artifact.json"
_SCHEMA_INDEX_PATH = _SCHEMA_ROOT / "index.json"
_SCHEMA_ID = OpenIdentifier("schema.artifact_catalog")
_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"


def _load_object(path: Path) -> dict[str, JsonValue]:
    """Load one committed UTF-8 JSON object document."""
    # Every independently addressable schema and collection index needs named
    # fields, so scalar or array roots are rejected before contract inspection.
    document: JsonValue = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise AssertionError(f"Expected a JSON object in {path}.")
    return document


def _adapter() -> SchemaValidatorAdapter:
    """Load the committed Catalog schema through the public toolchain."""
    # Checking identity and dialect before registration prevents a correct lookup
    # key from masking drift inside the distributed schema resource itself.
    schema = _load_object(_CATALOG_SCHEMA_PATH)
    assert schema.get("$id") == _SCHEMA_ID.value
    assert schema.get("$schema") == _SCHEMA_DIALECT
    return SchemaValidatorAdapter(SchemaLoader({_SCHEMA_ID: schema}))


def _artifact(artifact_id: str, source: dict[str, JsonValue]) -> JsonValue:
    """Create one minimal serialized Artifact catalog member."""
    # Fresh dictionaries preserve each scenario's order and isolate later source
    # mutation while sharing only the canonical field vocabulary.
    return {
        "id": artifact_id,
        "kind": {"id": "artifact.file"},
        "source": source,
    }


def test_artifact_catalog_schema_is_registered_and_exactly_scoped() -> None:
    """Verify stable discovery and the one-field Catalog object boundary."""
    schema = _load_object(_CATALOG_SCHEMA_PATH)
    index = _load_object(_SCHEMA_INDEX_PATH)
    properties = schema.get("properties")
    resources = index.get("resources")
    if not isinstance(properties, dict) or not isinstance(resources, list):
        raise AssertionError(
            "Catalog properties or schema index resources have invalid shapes."
        )

    # Catalog owns only ordered membership. References, lookup results, request
    # state, and protocol behavior remain outside this local resolution scope.
    assert "artifact-catalog.json" in resources
    assert frozenset(properties) == frozenset(("artifacts",))
    for unrelated_name in (
        "artifactId",
        "authorization",
        "extensions",
        "metadata",
        "references",
        "resolvedArtifacts",
        "task",
    ):
        assert unrelated_name not in properties


def test_artifact_catalog_schema_embeds_the_canonical_artifact_contract() -> None:
    """Verify the standalone Catalog cannot drift from the Artifact schema."""
    artifact_schema = _load_object(_ARTIFACT_SCHEMA_PATH)
    catalog_schema = _load_object(_CATALOG_SCHEMA_PATH)
    artifact_definitions = artifact_schema.pop("$defs", None)
    catalog_definitions = catalog_schema.get("$defs")
    if not isinstance(artifact_definitions, dict) or not isinstance(
        catalog_definitions, dict
    ):
        raise AssertionError("Artifact schema definitions must be objects.")

    # The Catalog root needs its own identity, so the embedded member consists of
    # the canonical Artifact root without $id/$schema plus the same flattened
    # definitions. Flattening keeps every local reference resolvable from one file.
    artifact_schema.pop("$id", None)
    artifact_schema.pop("$schema", None)
    embedded_artifact = catalog_definitions.get("artifact")
    embedded_definitions = {
        name: definition
        for name, definition in catalog_definitions.items()
        if name != "artifact"
    }
    assert embedded_artifact == artifact_schema
    assert embedded_definitions == artifact_definitions


def test_artifact_catalog_schema_accepts_empty_and_ordered_catalogs() -> None:
    """Verify explicit empty and heterogeneous ordered memberships are valid."""
    adapter = _adapter()
    empty: JsonValue = {"artifacts": []}
    artifacts: list[JsonValue] = [
        _artifact("inline-1", {"kind": "artifact.inline", "bytes": "00ff"}),
        _artifact(
            "uri-1",
            {
                "kind": "artifact.uri",
                "uri": {
                    "value": "https://content.example.test/item",
                    "isAbsolute": True,
                },
            },
        ),
        _artifact(
            "file-1",
            {"kind": "artifact.local_file", "path": "../content/item.bin"},
        ),
        _artifact(
            "custom-1",
            {"kind": "vendor.object_store", "objectKey": "objects/item"},
        ),
    ]
    complete: JsonValue = {"artifacts": artifacts}

    # The empty list is a concrete resolved state. A populated array validates
    # every member through the embedded contract without sorting or rewriting it.
    assert adapter.validate(_SCHEMA_ID, empty) == ()
    assert adapter.validate(_SCHEMA_ID, complete) == ()
    assert [artifact["id"] for artifact in artifacts if isinstance(artifact, dict)] == [
        "inline-1",
        "uri-1",
        "file-1",
        "custom-1",
    ]


def test_artifact_catalog_schema_preserves_duplicate_evidence() -> None:
    """Verify structural validation does not erase or preempt duplicate IDs."""
    adapter = _adapter()
    document: JsonValue = {
        "artifacts": [
            _artifact("duplicate", {"kind": "vendor.first"}),
            _artifact("duplicate", {"kind": "vendor.second"}),
        ]
    }

    # JSON Schema has no portable assertion for uniqueness of one object field.
    # Both members must survive so the dedicated Catalog validator can return the
    # stable duplicate_artifact_id domain error after deserialization.
    assert adapter.validate(_SCHEMA_ID, document) == ()
    assert isinstance(document, dict)
    members = document["artifacts"]
    assert isinstance(members, list)
    assert len(members) == 2


def test_artifact_catalog_schema_rejects_invalid_boundaries_stably() -> None:
    """Verify null, malformed members, and unrelated fields fail precisely."""
    adapter = _adapter()
    invalid_documents: tuple[
        tuple[JsonValue, tuple[SchemaValidationIssue, ...]], ...
    ] = (
        (
            {},
            (
                SchemaValidationIssue(
                    "/artifacts", "required", "Required property is missing."
                ),
            ),
        ),
        (
            {"artifacts": None},
            (
                SchemaValidationIssue(
                    "/artifacts", "type", "Value has an unexpected JSON type."
                ),
            ),
        ),
        (
            {"artifacts": [{"id": "missing-source", "kind": {"id": "artifact.file"}}]},
            (
                SchemaValidationIssue(
                    "/artifacts/0/source",
                    "required",
                    "Required property is missing.",
                ),
            ),
        ),
        (
            {"artifacts": [_artifact("invalid-inline", {"kind": "artifact.inline"})]},
            (
                SchemaValidationIssue(
                    "/artifacts/0/source",
                    "oneOf",
                    "Value must match exactly one schema alternative.",
                ),
            ),
        ),
        (
            {"artifacts": [], "scope": "global"},
            (
                SchemaValidationIssue(
                    "/scope",
                    "additionalProperties",
                    "Additional property is not allowed.",
                ),
            ),
        ),
    )

    # Exact issue tuples prove array indexes participate in stable JSON Pointer
    # paths and invalid members cannot bypass the canonical embedded contract.
    for document, expected in invalid_documents:
        assert adapter.validate(_SCHEMA_ID, document) == expected
