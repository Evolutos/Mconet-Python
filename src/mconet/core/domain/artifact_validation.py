"""Semantic validation for open artifact implementations."""

from __future__ import annotations

from collections.abc import Mapping
from io import IOBase, TextIOBase
from pathlib import Path
from typing import cast

from mconet.core.domain.artifact import Artifact
from mconet.core.domain.artifact_descriptor import ArtifactDescriptor
from mconet.core.domain.artifact_kind import ArtifactKind
from mconet.core.domain.artifact_source import ArtifactSource
from mconet.core.domain.authorization import Authorization
from mconet.core.domain.inline_artifact_source import InlineArtifactSource
from mconet.core.domain.json_value import JsonValue, validate_json_value_numbers
from mconet.core.domain.local_file_artifact_source import LocalFileArtifactSource
from mconet.core.domain.media_type import parse_media_type
from mconet.core.domain.open_identifier import OpenIdentifier, validate_open_identifier
from mconet.core.domain.uri import UriValue, validate_uri
from mconet.core.domain.uri_artifact_source import UriArtifactSource


def validate_artifact(artifact: Artifact) -> Artifact:
    """Validate one artifact description without accessing its content.

    Args:
        artifact: Any structural implementation of the Artifact protocol.

    Returns:
        The same artifact object after successful validation.

    Raises:
        TypeError: If the protocol surface or a field runtime type is invalid.
        ValueError: If identity, identifiers, source invariants, URI, media type,
            or portable JSON data violate their semantic contracts.

    Notes:
        Artifact ID uniqueness and reference resolution require an enclosing
        catalog and are intentionally excluded. Kind, descriptor, and media type
        remain open dimensions; runtime capability matching owns support policy.
    """
    candidate = cast(object, artifact)
    # Structural recognition keeps custom implementations open while requiring
    # the complete shared surface before any individual property is inspected.
    if not isinstance(candidate, Artifact):
        raise TypeError("artifact must implement Artifact.")

    artifact_id = cast(object, candidate.id)
    # Catalog-local IDs remain exact opaque text, but an empty or whitespace-only
    # value cannot participate in the later uniqueness and reference indexes.
    if not isinstance(artifact_id, str):
        raise TypeError("Artifact id must be a string.")
    if not artifact_id or artifact_id.isspace():
        raise ValueError("Artifact id must not be empty or whitespace.")

    _validate_artifact_kind(cast(object, candidate.kind))
    _validate_artifact_source(cast(object, candidate.source))
    _validate_artifact_descriptor(cast(object, candidate.descriptor))
    _validate_media_type(cast(object, candidate.media_type))
    _validate_json_mapping(cast(object, candidate.metadata), "metadata")
    _validate_json_mapping(cast(object, candidate.extensions), "extensions")
    return candidate


def _validate_artifact_kind(value: object) -> None:
    """Validate the shared fields of an open ArtifactKind implementation."""
    # The complete protocol preserves semantic and extension data for unknown
    # kinds instead of accepting an identifier-only lossy representation.
    if not isinstance(value, ArtifactKind):
        raise TypeError("Artifact kind must implement ArtifactKind.")

    identifier = cast(object, value.id)
    semantic = cast(object, value.semantic)
    _validate_identifier(identifier, "Artifact kind id")
    # Optional semantic guidance is opaque producer text and is not inferred
    # from a standard identifier or used as a capability decision.
    if semantic is not None and not isinstance(semantic, str):
        raise TypeError("Artifact kind semantic must be a string or None.")
    _validate_json_mapping(cast(object, value.extensions), "kind extensions")


def _validate_artifact_source(value: object) -> None:
    """Validate an open source identity and known concrete source invariants."""
    # Unknown sources need only satisfy the shared descriptive protocol. Known
    # SDK values receive their full concrete validation without accessing data.
    if not isinstance(value, ArtifactSource):
        raise TypeError("Artifact source must implement ArtifactSource.")

    identifier = cast(object, value.kind)
    _validate_identifier(identifier, "Artifact source kind")

    if isinstance(value, InlineArtifactSource):
        _validate_fixed_source_kind(
            identifier, "artifact.inline", "InlineArtifactSource"
        )
        _validate_inline_source(value)
    elif isinstance(value, UriArtifactSource):
        _validate_fixed_source_kind(identifier, "artifact.uri", "UriArtifactSource")
        _validate_uri_source(value)
    elif isinstance(value, LocalFileArtifactSource):
        _validate_fixed_source_kind(
            identifier,
            "artifact.local_file",
            "LocalFileArtifactSource",
        )
        _validate_local_file_source(value)


def _validate_inline_source(source: InlineArtifactSource) -> None:
    """Require immutable bytes without reading or transforming the payload."""
    value = cast(object, source.bytes)
    # Bytes is nominally distinct to static callers but uses built-in bytes at
    # runtime; mutable buffers and alternate representations remain invalid.
    if not isinstance(value, bytes):
        raise TypeError("InlineArtifactSource bytes must be a Bytes value.")


def _validate_uri_source(source: UriArtifactSource) -> None:
    """Validate URI syntax and opaque authorization identity without resolving it."""
    uri = cast(object, source.uri)
    authorization = cast(object, source.authorization)
    if not isinstance(uri, UriValue):
        raise TypeError("UriArtifactSource uri must be a UriValue.")

    # URI validation is lexical only. Relative references remain valid and no
    # scheme handler, DNS lookup, download, or filesystem access occurs here.
    validate_uri(uri)
    if authorization is None:
        return
    if not isinstance(authorization, Authorization):
        raise TypeError(
            "UriArtifactSource authorization must implement Authorization or be None."
        )

    # Only handler-selection identity is observable; credential fields remain
    # opaque and are never copied, serialized, compared, or logged.
    _validate_identifier(
        cast(object, authorization.kind),
        "UriArtifactSource authorization kind",
    )


def _validate_local_file_source(source: LocalFileArtifactSource) -> None:
    """Validate one local locator without touching the path or file handle."""
    path = cast(object, source.path)
    file_handle = cast(object, source.file_handle)
    # Exactly one representation is required before a later reader can select a
    # deterministic access path; neither branch performs a resource operation.
    if (path is None) == (file_handle is None):
        raise ValueError(
            "LocalFileArtifactSource requires exactly one of path or file_handle."
        )
    if path is not None and not isinstance(path, Path):
        raise TypeError("LocalFileArtifactSource path must be a Path or None.")

    # Runtime recognition deliberately avoids read, seek, fileno, stat, closed,
    # and mode probes. Known text streams are excluded without consuming data.
    if file_handle is not None and (
        not isinstance(file_handle, IOBase) or isinstance(file_handle, TextIOBase)
    ):
        raise TypeError(
            "LocalFileArtifactSource file_handle must be a BinaryIO or None."
        )


def _validate_fixed_source_kind(
    value: object,
    expected: str,
    source_name: str,
) -> None:
    """Require a concrete SDK source to retain its fixed representation kind."""
    # The caller already validated nominal identifier syntax. Exact identity now
    # prevents a concrete value from masquerading as another reader contract.
    identifier = cast(OpenIdentifier, value)
    if identifier.value != expected:
        raise ValueError(f"{source_name} kind must be {expected}.")


def _validate_artifact_descriptor(value: object) -> None:
    """Validate an optional open descriptor through its common identity field."""
    if value is None:
        return
    # Modality-specific fields remain owned by concrete descriptor validators;
    # the shared contract only guarantees one portable open shape identifier.
    if not isinstance(value, ArtifactDescriptor):
        raise TypeError(
            "Artifact descriptor must implement ArtifactDescriptor or be None."
        )
    _validate_identifier(cast(object, value.kind), "Artifact descriptor kind")


def _validate_media_type(value: object) -> None:
    """Validate optional media type syntax without normalizing stored text."""
    if value is None:
        return
    if not isinstance(value, str):
        raise TypeError("Artifact media_type must be a string or None.")

    # Parsing provides the single RFC-aware syntax boundary. The parsed object is
    # intentionally discarded so validation cannot rewrite the artifact value.
    parse_media_type(value)


def _validate_identifier(value: object, field_name: str) -> None:
    """Require and validate one portable OpenIdentifier field."""
    # Nominal type checking produces a field-specific error before the shared
    # grammar validator reports casing, whitespace, or namespace violations.
    if not isinstance(value, OpenIdentifier):
        raise TypeError(f"{field_name} must be an OpenIdentifier.")
    validate_open_identifier(value)


def _validate_json_mapping(value: object, field_name: str) -> None:
    """Require a string-keyed mapping containing portable JSON values."""
    # Mapping keeps read-only and custom implementations valid while excluding
    # sequences and scalar alternatives to the language-neutral object shape.
    if not isinstance(value, Mapping):
        raise TypeError(f"Artifact {field_name} must be a mapping.")
    mapping = cast(Mapping[object, object], value)
    if any(not isinstance(key, str) for key in mapping):
        raise TypeError(f"Artifact {field_name} keys must be strings.")

    # Validate values separately because an arbitrary Mapping is not itself a
    # concrete dict branch of JsonValue; unknown keys remain uninterpreted.
    for raw_value in mapping.values():
        validate_json_value_numbers(cast(JsonValue, raw_value))
