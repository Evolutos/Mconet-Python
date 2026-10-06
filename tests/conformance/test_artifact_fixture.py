"""Conformance checks for language-neutral Artifact Golden fixtures."""

from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import ExitStack
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from types import MappingProxyType
from unittest.mock import patch

from mconet.core.domain import (
    Artifact,
    ArtifactCatalog,
    ArtifactDescriptor,
    ArtifactKind,
    ArtifactMetadata,
    ArtifactReference,
    ArtifactSource,
    Bytes,
    Extensions,
    InlineArtifactSource,
    JsonValue,
    LocalFileArtifactSource,
    ModelInteractionError,
    OpenIdentifier,
    UriArtifactSource,
    UriValue,
    resolve_artifact_reference,
    validate_artifact,
    validate_artifact_catalog,
)
from mconet.testing import (
    SchemaLoader,
    SchemaValidatorAdapter,
    json_fixtures_equal,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_FIXTURE_PATH = _PROJECT_ROOT / "spec" / "fixtures" / "r1-text-unary" / "artifact.json"
_INDEX_PATH = _FIXTURE_PATH.parent / "index.json"
_ARTIFACT_SCHEMA_PATH = _PROJECT_ROOT / "spec" / "schemas" / "artifact.json"
_CATALOG_SCHEMA_PATH = _PROJECT_ROOT / "spec" / "schemas" / "artifact-catalog.json"
_ARTIFACT_SCHEMA_ID = OpenIdentifier("schema.artifact")
_CATALOG_SCHEMA_ID = OpenIdentifier("schema.artifact_catalog")
_EMPTY_EXTENSIONS: Extensions = MappingProxyType({})


def _empty_extensions() -> Extensions:
    """Return immutable empty data for omitted fixture mappings."""
    # The shared proxy has no nested members and rejects mutation, so independent
    # reconstructed values cannot leak fixture state through their defaults.
    return _EMPTY_EXTENSIONS


@dataclass(frozen=True, slots=True)
class _FixtureKind:
    """Represent one open Artifact Kind decoded from shared JSON."""

    id: OpenIdentifier
    """Standard or provider-defined semantic identity."""

    semantic: str | None = None
    """Optional producer guidance retained without interpretation."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Unknown portable Kind data preserved during round trips."""


@dataclass(frozen=True, slots=True)
class _FixtureArtifact:
    """Provide a complete structural Artifact reconstructed from a case."""

    id: str
    """Identity local to one enclosing Catalog."""

    kind: ArtifactKind
    """Open semantic classification retained independently from Source."""

    media_type: str | None
    """Optional declared media type preserved as exact text."""

    source: ArtifactSource
    """Data-only content origin decoded from one supported fixture shape."""

    descriptor: ArtifactDescriptor | None = None
    """Optional modality facts, absent from the current shared cases."""

    metadata: ArtifactMetadata = field(default_factory=_empty_extensions)
    """Portable intrinsic Artifact data."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Unknown portable Artifact fields."""


def _load_object(path: Path) -> dict[str, JsonValue]:
    """Load one committed UTF-8 JSON document and require an object root."""
    document: JsonValue = json.loads(path.read_text(encoding="utf-8"))
    # A named envelope prevents language implementations from inventing
    # positional semantics for an invalid top-level array or scalar.
    if not isinstance(document, dict):
        raise AssertionError(f"Expected a JSON object in {path}.")
    return document


def _require_object(value: JsonValue | None, field_name: str) -> dict[str, JsonValue]:
    """Return one required object-valued fixture field."""
    # Missing, null, array, and scalar values fail before domain reconstruction
    # can apply host-language casts or access nested fields.
    if not isinstance(value, dict):
        raise AssertionError(f"{field_name} must be a JSON object.")
    return value


def _require_array(value: JsonValue | None, field_name: str) -> list[JsonValue]:
    """Return one required array-valued fixture field in source order."""
    # Arrays preserve case and Catalog membership order across implementations;
    # converting either collection to a set or mapping would erase evidence.
    if not isinstance(value, list):
        raise AssertionError(f"{field_name} must be a JSON array.")
    return value


def _require_string(value: JsonValue | None, field_name: str) -> str:
    """Return one required string without implicit coercion."""
    # JSON numbers, booleans, null, and containers must not acquire different
    # textual identities through platform-specific conversion rules.
    if not isinstance(value, str):
        raise AssertionError(f"{field_name} must be a JSON string.")
    return value


def _require_boolean(value: JsonValue | None, field_name: str) -> bool:
    """Return one required exact JSON boolean value."""
    # Exact type checking keeps integer 0/1 distinct from JSON false/true despite
    # Python's bool subclassing int at runtime.
    if type(value) is not bool:
        raise AssertionError(f"{field_name} must be a JSON boolean.")
    return value


def _optional_string(value: JsonValue | None, field_name: str) -> str | None:
    """Return an optional nullable string and reject every other JSON kind."""
    # Omission and explicit null both map to the domain's None representation;
    # any present non-string value remains a malformed fixture boundary.
    if value is not None and not isinstance(value, str):
        raise AssertionError(f"{field_name} must be a JSON string or null.")
    return value


def _mapping_or_empty(
    document: dict[str, JsonValue],
    field_name: str,
) -> Extensions:
    """Decode an omitted portable mapping as immutable empty data."""
    # Present objects remain uninterpreted until public Artifact validation checks
    # recursive JSON number portability; absence does not invent any fields.
    if field_name not in document:
        return _EMPTY_EXTENSIONS
    return _require_object(document[field_name], field_name)


def _decode_kind(value: JsonValue | None) -> _FixtureKind:
    """Decode one open Artifact Kind without using a known-value registry."""
    document = _require_object(value, "kind")
    # Wrapping the exact ID preserves provider-defined values while allowing the
    # public Artifact validator to apply the common identifier contract.
    return _FixtureKind(
        id=OpenIdentifier(_require_string(document.get("id"), "kind.id")),
        semantic=_optional_string(document.get("semantic"), "kind.semantic"),
        extensions=_mapping_or_empty(document, "extensions"),
    )


def _decode_source(value: JsonValue | None) -> ArtifactSource:
    """Decode one safe concrete Source without accessing its content."""
    document = _require_object(value, "source")
    kind = _require_string(document.get("kind"), "source.kind")

    # Inline content uses canonical lowercase hexadecimal in JSON and becomes an
    # immutable Bytes value; decoding performs no external operation.
    if kind == "artifact.inline":
        encoded = _require_string(document.get("bytes"), "source.bytes")
        return InlineArtifactSource(Bytes(bytes.fromhex(encoded)))

    # URI text and its declared form are reconstructed independently so domain
    # validation can check their consistency without normalizing or fetching it.
    if kind == "artifact.uri":
        uri = _require_object(document.get("uri"), "source.uri")
        return UriArtifactSource(
            UriValue(
                _require_string(uri.get("value"), "source.uri.value"),
                _require_boolean(uri.get("isAbsolute"), "source.uri.isAbsolute"),
            )
        )

    # Local paths remain lexical Path values. Construction deliberately avoids
    # exists, stat, resolve, open, read, or any filesystem ownership decision.
    if kind == "artifact.local_file":
        return LocalFileArtifactSource(
            path=Path(_require_string(document.get("path"), "source.path"))
        )
    raise AssertionError(f"Unsupported Artifact fixture source kind: {kind}.")


def _decode_artifact(document: dict[str, JsonValue]) -> Artifact:
    """Reconstruct and validate one schema-valid Artifact document."""
    # Fixture decoding maps every shared field independently; it never derives
    # Kind from media type or Source representation from semantic classification.
    artifact = _FixtureArtifact(
        id=_require_string(document.get("id"), "artifact.id"),
        kind=_decode_kind(document.get("kind")),
        media_type=_optional_string(document.get("mediaType"), "artifact.mediaType"),
        source=_decode_source(document.get("source")),
        metadata=_mapping_or_empty(document, "metadata"),
        extensions=_mapping_or_empty(document, "extensions"),
    )
    return validate_artifact(artifact)


def _decode_catalog(document: dict[str, JsonValue]) -> ArtifactCatalog:
    """Reconstruct one ordered Catalog without preempting duplicate validation."""
    members = _require_array(document.get("artifacts"), "catalog.artifacts")
    # Artifact construction validates each member, while Catalog construction
    # deliberately retains duplicate IDs for the dedicated validator or resolver.
    return ArtifactCatalog(
        tuple(
            _decode_artifact(_require_object(member, "catalog.artifacts[]"))
            for member in members
        )
    )


def _decode_reference(document: dict[str, JsonValue]) -> ArtifactReference:
    """Decode one Catalog-local reference without resolving it implicitly."""
    relation = _optional_string(document.get("relation"), "reference.relation")
    # Relation and metadata describe this occurrence but cannot select another
    # Catalog or alter exact ID matching during explicit resolution.
    return ArtifactReference(
        artifact_id=_require_string(document.get("artifactId"), "reference.artifactId"),
        relation=OpenIdentifier(relation) if relation is not None else None,
        metadata=_mapping_or_empty(document, "metadata"),
    )


def _serialize_kind(kind: ArtifactKind) -> dict[str, JsonValue]:
    """Serialize one open Kind without normalizing provider-owned fields."""
    document: dict[str, JsonValue] = {"id": kind.id.value}
    # Optional semantics and extensions are emitted only when present, preserving
    # the schema's omission contract and all uninterpreted JSON values.
    if kind.semantic is not None:
        document["semantic"] = kind.semantic
    if kind.extensions:
        document["extensions"] = dict(kind.extensions)
    return document


def _serialize_source(source: ArtifactSource) -> dict[str, JsonValue]:
    """Serialize one known Source without reading or resolving its content."""
    # Inline bytes are already memory-resident and canonical hex produces a
    # deterministic lowercase representation without a text encoding guess.
    if isinstance(source, InlineArtifactSource):
        return {"kind": source.kind.value, "bytes": bytes(source.bytes).hex()}

    # URI serialization copies the exact retained reference and declaration;
    # optional Authorization remains runtime-only and is never inspected.
    if isinstance(source, UriArtifactSource):
        return {
            "kind": source.kind.value,
            "uri": {
                "value": source.uri.value,
                "isAbsolute": source.uri.is_absolute,
            },
        }

    # Fixture local sources use paths only. as_posix keeps the committed lexical
    # separator stable across host operating systems and performs no filesystem I/O.
    if isinstance(source, LocalFileArtifactSource):
        if source.path is None or source.file_handle is not None:
            raise AssertionError("Artifact fixture local source must contain one path.")
        return {"kind": source.kind.value, "path": source.path.as_posix()}
    raise AssertionError(f"Unsupported Artifact fixture Source: {source.kind.value}.")


def _serialize_artifact(artifact: Artifact) -> dict[str, JsonValue]:
    """Serialize shared Artifact fields for deterministic round-trip checks."""
    document: dict[str, JsonValue] = {
        "id": artifact.id,
        "kind": _serialize_kind(artifact.kind),
        "source": _serialize_source(artifact.source),
    }
    # Optional values remain omitted when absent; mapping values are copied as
    # portable JSON without interpreting producer-specific keys.
    if artifact.media_type is not None:
        document["mediaType"] = artifact.media_type
    if artifact.descriptor is not None:
        raise AssertionError("Current Artifact fixtures do not encode descriptors.")
    if artifact.metadata:
        document["metadata"] = dict(artifact.metadata)
    if artifact.extensions:
        document["extensions"] = dict(artifact.extensions)
    return document


def _serialize_reference(reference: ArtifactReference) -> dict[str, JsonValue]:
    """Serialize one reference without adding resolved Artifact state."""
    document: dict[str, JsonValue] = {"artifactId": reference.artifact_id}
    # Relation and metadata retain their independent optional representations;
    # the target object itself never becomes part of reference JSON.
    if reference.relation is not None:
        document["relation"] = reference.relation.value
    if reference.metadata:
        document["metadata"] = dict(reference.metadata)
    return document


def _adapter(path: Path, schema_id: OpenIdentifier) -> SchemaValidatorAdapter:
    """Load one committed Artifact schema through the public test adapter."""
    schema = _load_object(path)
    # Fixture-selected identity must equal the resource identity before cases can
    # provide conformance evidence for this exact schema.
    assert schema.get("$id") == schema_id.value
    return SchemaValidatorAdapter(SchemaLoader({schema_id: schema}))


def _case_object(value: JsonValue, group_name: str) -> dict[str, JsonValue]:
    """Return one named case object from a declared fixture group."""
    case = _require_object(value, group_name)
    # Requiring a stable non-coerced name makes every failure traceable without
    # allowing the name to alter domain reconstruction or expected outcomes.
    _require_string(case.get("name"), f"{group_name}.name")
    return case


def _error_document(error: ModelInteractionError) -> dict[str, JsonValue]:
    """Project one normalized failure onto portable expected fields."""
    # Service status, request identity, recovery, and cause are intentionally
    # excluded because these domain failures have no external interaction data.
    return {
        "category": error.category.id.value,
        "phase": error.phase.id.value,
        "code": error.code,
        "message": error.message,
    }


def _capture_error(action: Callable[[], object]) -> ModelInteractionError:
    """Return the normalized error raised by one fixture action."""
    # A narrow catch ensures unrelated construction or assertion failures cannot
    # satisfy an expected domain-error case accidentally.
    try:
        action()
    except ModelInteractionError as error:
        return error
    raise AssertionError("Expected ModelInteractionError to be raised.")


def test_artifact_fixture_is_registered_with_a_stable_envelope() -> None:
    """Verify discovery metadata and all required case groups are explicit."""
    fixture = _load_object(_FIXTURE_PATH)
    index = _load_object(_INDEX_PATH)

    # Exact envelope fields expose incompatible format drift, while index
    # registration ensures other platform runners can discover the resource.
    assert "artifact.json" in _require_array(index.get("resources"), "resources")
    assert frozenset(fixture) == frozenset(
        {
            "artifactSchemaId",
            "catalogSchemaId",
            "duplicateIdCases",
            "format_version",
            "referenceCases",
            "sourceCases",
            "unknownKindCases",
        }
    )
    assert fixture["format_version"] == 1
    assert fixture["artifactSchemaId"] == _ARTIFACT_SCHEMA_ID.value
    assert fixture["catalogSchemaId"] == _CATALOG_SCHEMA_ID.value

    # Every required behavior has independent non-empty evidence, and case names
    # remain globally unique for deterministic reporting across implementations.
    names: list[str] = []
    for group_name in (
        "duplicateIdCases",
        "referenceCases",
        "sourceCases",
        "unknownKindCases",
    ):
        cases = _require_array(fixture.get(group_name), group_name)
        assert cases
        names.extend(
            _require_string(
                _case_object(case, f"{group_name}[]").get("name"),
                f"{group_name}[].name",
            )
            for case in cases
        )
    assert len(names) == len(set(names))


def test_artifact_source_cases_round_trip_without_source_io() -> None:
    """Verify inline, URI, and local-file Sources remain exact and data-only."""
    fixture = _load_object(_FIXTURE_PATH)
    cases = _require_array(fixture.get("sourceCases"), "sourceCases")
    adapter = _adapter(_ARTIFACT_SCHEMA_PATH, _ARTIFACT_SCHEMA_ID)
    source_types: list[type[object]] = []

    # Block every ordinary metadata, normalization, and content-access method
    # after committed resources are loaded. Fixture handling may retain the path
    # lexically but cannot inspect or resolve its filesystem target.
    with ExitStack() as filesystem_guards:
        for method_name in ("exists", "is_file", "open", "resolve", "stat"):
            filesystem_guards.enter_context(
                patch.object(
                    Path,
                    method_name,
                    side_effect=AssertionError(
                        "Artifact fixture validation must not access paths."
                    ),
                )
            )
        for case_value in cases:
            case = _case_object(case_value, "sourceCases[]")
            document = _require_object(case.get("input"), "sourceCases[].input")
            expected = _require_object(case.get("expected"), "sourceCases[].expected")
            assert adapter.validate(_ARTIFACT_SCHEMA_ID, document) == ()

            artifact = _decode_artifact(document)
            source_types.append(type(artifact.source))
            assert json_fixtures_equal(_serialize_artifact(artifact), expected)

    # Exact type order confirms each required representation is independently
    # exercised instead of falling through one generic open Source branch.
    assert source_types == [
        InlineArtifactSource,
        UriArtifactSource,
        LocalFileArtifactSource,
    ]


def test_artifact_unknown_kind_round_trips_without_registry_mapping() -> None:
    """Verify provider-defined Kind identity and data survive unchanged."""
    fixture = _load_object(_FIXTURE_PATH)
    cases = _require_array(fixture.get("unknownKindCases"), "unknownKindCases")
    adapter = _adapter(_ARTIFACT_SCHEMA_PATH, _ARTIFACT_SCHEMA_ID)

    # Schema and domain validation accept the same open Kind. Serialization must
    # reproduce semantic, extension, metadata, and Artifact extension data exactly.
    for case_value in cases:
        case = _case_object(case_value, "unknownKindCases[]")
        document = _require_object(case.get("input"), "unknownKindCases[].input")
        expected = _require_object(case.get("expected"), "unknownKindCases[].expected")
        assert adapter.validate(_ARTIFACT_SCHEMA_ID, document) == ()
        artifact = _decode_artifact(document)
        assert artifact.kind.id == OpenIdentifier("vendor.depth_map")
        assert artifact.kind.semantic == "Depth values aligned to an image plane."
        assert artifact.kind.extensions == {"vendor.version": 2}
        assert json_fixtures_equal(_serialize_artifact(artifact), expected)


def test_artifact_reference_cases_use_only_the_supplied_catalog() -> None:
    """Verify successful and missing references have portable exact outcomes."""
    fixture = _load_object(_FIXTURE_PATH)
    cases = _require_array(fixture.get("referenceCases"), "referenceCases")
    adapter = _adapter(_CATALOG_SCHEMA_PATH, _CATALOG_SCHEMA_ID)

    for case_value in cases:
        case = _case_object(case_value, "referenceCases[]")
        catalog_document = _require_object(
            case.get("catalog"), "referenceCases[].catalog"
        )
        reference_document = _require_object(
            case.get("reference"), "referenceCases[].reference"
        )
        assert adapter.validate(_CATALOG_SCHEMA_ID, catalog_document) == ()
        catalog = _decode_catalog(catalog_document)
        assert validate_artifact_catalog(catalog) is catalog
        reference = _decode_reference(reference_document)
        assert json_fixtures_equal(_serialize_reference(reference), reference_document)

        # Success resolves the original member identity. Failure compares every
        # portable normalized field and cannot fall back to another Catalog.
        if "expectedArtifactId" in case:
            expected_id = _require_string(
                case.get("expectedArtifactId"), "referenceCases[].expectedArtifactId"
            )
            resolved = resolve_artifact_reference(reference, catalog)
            assert resolved.id == expected_id
            assert resolved is next(
                artifact for artifact in catalog.artifacts if artifact.id == expected_id
            )
            assert "expectedError" not in case
        else:
            expected_error = _require_object(
                case.get("expectedError"), "referenceCases[].expectedError"
            )
            other_catalog_document = _require_object(
                case.get("otherCatalog"), "referenceCases[].otherCatalog"
            )
            assert adapter.validate(_CATALOG_SCHEMA_ID, other_catalog_document) == ()
            other_catalog = _decode_catalog(other_catalog_document)

            # The same reference succeeds only when that other scope is supplied
            # explicitly; its presence cannot influence lookup in the first scope.
            assert resolve_artifact_reference(reference, other_catalog).id == (
                reference.artifact_id
            )
            error = _capture_error(
                partial(resolve_artifact_reference, reference, catalog)
            )
            assert json_fixtures_equal(_error_document(error), expected_error)
            assert "expectedArtifactId" not in case


def test_artifact_duplicate_id_cases_return_stable_error_before_lookup() -> None:
    """Verify duplicate evidence survives schema decoding and preempts resolution."""
    fixture = _load_object(_FIXTURE_PATH)
    cases = _require_array(fixture.get("duplicateIdCases"), "duplicateIdCases")
    adapter = _adapter(_CATALOG_SCHEMA_PATH, _CATALOG_SCHEMA_ID)

    # Catalog schema intentionally preserves duplicate members because semantic
    # uniqueness and its normalized error belong to the Catalog validator.
    for case_value in cases:
        case = _case_object(case_value, "duplicateIdCases[]")
        catalog_document = _require_object(
            case.get("catalog"), "duplicateIdCases[].catalog"
        )
        reference_document = _require_object(
            case.get("reference"), "duplicateIdCases[].reference"
        )
        expected_error = _require_object(
            case.get("expectedError"), "duplicateIdCases[].expectedError"
        )
        assert adapter.validate(_CATALOG_SCHEMA_ID, catalog_document) == ()

        catalog = _decode_catalog(catalog_document)
        reference = _decode_reference(reference_document)
        assert len(catalog.artifacts) == 2
        assert catalog.artifacts[0].id == catalog.artifacts[1].id
        error = _capture_error(partial(resolve_artifact_reference, reference, catalog))
        assert json_fixtures_equal(_error_document(error), expected_error)
