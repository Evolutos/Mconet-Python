"""Catalog-local resolution for immutable artifact references."""

from __future__ import annotations

from typing import cast

from mconet.core.domain.artifact import Artifact
from mconet.core.domain.artifact_catalog import ArtifactCatalog
from mconet.core.domain.artifact_catalog_validation import validate_artifact_catalog
from mconet.core.domain.artifact_reference import ArtifactReference
from mconet.core.domain.error_category import ErrorCategory
from mconet.core.domain.interaction_phase import InteractionPhase
from mconet.core.domain.model_interaction_error import ModelInteractionError
from mconet.core.domain.open_identifier import OpenIdentifier

_INVALID_REQUEST_CATEGORY = ErrorCategory(OpenIdentifier("invalid_request"))
_ARTIFACT_RESOLUTION_PHASE = InteractionPhase(OpenIdentifier("artifact_resolution"))
_REFERENCE_NOT_FOUND_CODE = "artifact_reference_not_found"
_REFERENCE_NOT_FOUND_MESSAGE = (
    "ArtifactReference does not match an artifact in the supplied catalog."
)


def resolve_artifact_reference(
    reference: ArtifactReference,
    catalog: ArtifactCatalog,
) -> Artifact:
    """Resolve one reference only within the explicitly supplied catalog.

    Args:
        reference: The immutable catalog-local reference to resolve.
        catalog: The single validated lookup scope for this operation.

    Returns:
        The exact Artifact object whose ID equals ``reference.artifact_id``.

    Raises:
        TypeError: If the reference, ID storage, catalog, or members are invalid.
        ValueError: If a catalog member violates Artifact semantics.
        ModelInteractionError: If the catalog has duplicate IDs or no matching
            member. Missing references use ``artifact_reference_not_found``.

    Notes:
        Matching is exact and case-sensitive. Relation and metadata describe the
        reference occurrence but do not alter target selection. No global scope,
        fallback catalog, cache, or content access participates in resolution.
    """
    candidate = cast(object, reference)
    # The concrete value owns reference storage and metadata invariants; requiring
    # it prevents arbitrary objects from supplying a coincidental artifact_id.
    if not isinstance(candidate, ArtifactReference):
        raise TypeError("reference must be an ArtifactReference.")

    artifact_id = cast(object, candidate.artifact_id)
    # Recheck the primitive field because untyped deserializers can bypass frozen
    # construction. Empty strings remain ordinary unmatched IDs rather than a
    # second missing-value representation.
    if not isinstance(artifact_id, str):
        raise TypeError("ArtifactReference artifact_id must be a string.")

    validated_catalog = validate_artifact_catalog(catalog)
    # Catalog validation guarantees complete Artifacts and unique string IDs, so
    # the first equality match is unambiguous and can be returned by identity.
    for artifact in validated_catalog.artifacts:
        if artifact.id == artifact_id:
            return artifact

    raise _artifact_reference_not_found_error()


def _artifact_reference_not_found_error() -> ModelInteractionError:
    """Create the normalized error for an unresolved catalog-local reference."""
    # Omit the producer ID from exception text so control characters or sensitive
    # application labels cannot flow into logs through a lookup failure.
    return ModelInteractionError(
        category=_INVALID_REQUEST_CATEGORY,
        phase=_ARTIFACT_RESOLUTION_PHASE,
        code=_REFERENCE_NOT_FOUND_CODE,
        message=_REFERENCE_NOT_FOUND_MESSAGE,
    )
