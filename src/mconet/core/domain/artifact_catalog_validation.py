"""Catalog-local validation for ordered artifact collections."""

from __future__ import annotations

from typing import cast

from mconet.core.domain.artifact import Artifact
from mconet.core.domain.artifact_catalog import ArtifactCatalog
from mconet.core.domain.artifact_validation import validate_artifact
from mconet.core.domain.error_category import ErrorCategory
from mconet.core.domain.interaction_phase import InteractionPhase
from mconet.core.domain.model_interaction_error import ModelInteractionError
from mconet.core.domain.open_identifier import OpenIdentifier

_INVALID_REQUEST_CATEGORY = ErrorCategory(OpenIdentifier("invalid_request"))
_VALIDATION_PHASE = InteractionPhase(OpenIdentifier("validation"))
_DUPLICATE_ARTIFACT_ID_CODE = "duplicate_artifact_id"
_DUPLICATE_ARTIFACT_ID_MESSAGE = "ArtifactCatalog artifact IDs must be unique."


def validate_artifact_catalog(catalog: ArtifactCatalog) -> ArtifactCatalog:
    """Validate every artifact and require unique IDs within this catalog.

    Args:
        catalog: The immutable ordered catalog to validate.

    Returns:
        The same catalog object after successful validation.

    Raises:
        TypeError: If ``catalog`` or its immutable member storage is invalid.
        ValueError: If an individual artifact violates its domain semantics.
        ModelInteractionError: If two members use the same catalog-local ID;
            its stable code is ``duplicate_artifact_id``.

    Notes:
        Uniqueness is scoped to this one catalog. The function does not resolve
        ArtifactReference values, inspect other catalogs, or access content.
    """
    candidate = cast(object, catalog)
    # Require the concrete catalog because this validator owns its tuple storage
    # and local-scope invariants rather than an open structural protocol.
    if not isinstance(candidate, ArtifactCatalog):
        raise TypeError("catalog must be an ArtifactCatalog.")

    artifacts = cast(object, candidate.artifacts)
    # Recheck tuple storage at the external trust boundary so dynamically
    # corrupted frozen values cannot change membership during validation.
    if not isinstance(artifacts, tuple):
        raise TypeError("ArtifactCatalog artifacts must be a tuple.")

    artifact_ids: set[str] = set()
    for artifact in cast(tuple[object, ...], artifacts):
        # Member type is checked before the dedicated validator so an unrelated
        # object receives a catalog-specific diagnostic without attribute access.
        if not isinstance(artifact, Artifact):
            raise TypeError("ArtifactCatalog artifacts must contain Artifact values.")
        validated = validate_artifact(artifact)
        artifact_id = validated.id

        # Set membership makes duplicate detection linear while retaining the
        # catalog's original tuple order and first-failure traversal semantics.
        if artifact_id in artifact_ids:
            raise _duplicate_artifact_id_error()
        artifact_ids.add(artifact_id)

    return candidate


def _duplicate_artifact_id_error() -> ModelInteractionError:
    """Create the normalized error for one catalog-local duplicate ID."""
    # The message deliberately omits the producer ID so control characters or
    # application-sensitive labels cannot enter logs through exception text.
    return ModelInteractionError(
        category=_INVALID_REQUEST_CATEGORY,
        phase=_VALIDATION_PHASE,
        code=_DUPLICATE_ARTIFACT_ID_CODE,
        message=_DUPLICATE_ARTIFACT_ID_MESSAGE,
    )
