"""Supported execution scope validation for artifact catalogs."""

from __future__ import annotations

from typing import cast

from mconet.core.domain.artifact_catalog import ArtifactCatalog
from mconet.core.domain.artifact_catalog_validation import validate_artifact_catalog
from mconet.core.domain.error_category import ErrorCategory
from mconet.core.domain.interaction_phase import InteractionPhase
from mconet.core.domain.model_interaction_error import ModelInteractionError
from mconet.core.domain.open_identifier import OpenIdentifier

_UNSUPPORTED_FEATURE_CATEGORY = ErrorCategory(OpenIdentifier("unsupported_feature"))
_VALIDATION_PHASE = InteractionPhase(OpenIdentifier("validation"))
_UNSUPPORTED_MESSAGE_CONTENT_CODE = "unsupported_message_content"
_UNSUPPORTED_ARTIFACT_CATALOG_MESSAGE = "Only an empty ArtifactCatalog is supported."


def validate_empty_artifact_catalog_scope(
    catalog: ArtifactCatalog,
) -> ArtifactCatalog:
    """Require a fully valid artifact catalog to contain no artifacts.

    Args:
        catalog: The immutable catalog-local artifact scope to inspect.

    Returns:
        The same catalog object when its validated artifact tuple is empty.

    Raises:
        TypeError: If the catalog or its dynamically observed storage is invalid.
        ValueError: If an artifact violates its domain contract.
        ModelInteractionError: If IDs are duplicated or a valid catalog is
            non-empty. The latter uses ``unsupported_message_content``.

    Notes:
        Catalog and member validation run before the support-policy decision.
        This gate never resolves references or reads, opens, fetches, uploads,
        transforms, or otherwise accesses artifact content.
    """
    # Complete validation has sole ownership of member shape, Artifact semantics,
    # and catalog-local ID uniqueness. Preserve those precise failures instead of
    # labeling malformed input merely as an unsupported execution feature.
    validated = validate_artifact_catalog(catalog)
    artifacts = cast(object, validated.artifacts)

    # Recheck immutable tuple storage at the use point. Untyped code can bypass a
    # frozen dataclass, and a post-validation replacement must not reach a truthy
    # scope check with a different container contract.
    if not isinstance(artifacts, tuple):
        raise TypeError("ArtifactCatalog artifacts must be a tuple.")
    if artifacts:
        raise _unsupported_artifact_catalog_error()
    return validated


def _unsupported_artifact_catalog_error() -> ModelInteractionError:
    """Create the normalized failure for one non-empty artifact catalog."""
    # Keep the message independent of member count, IDs, Kinds, sources, paths,
    # URIs, metadata, and extensions so producer data cannot leak through errors.
    return ModelInteractionError(
        category=_UNSUPPORTED_FEATURE_CATEGORY,
        phase=_VALIDATION_PHASE,
        code=_UNSUPPORTED_MESSAGE_CONTENT_CODE,
        message=_UNSUPPORTED_ARTIFACT_CATALOG_MESSAGE,
    )
