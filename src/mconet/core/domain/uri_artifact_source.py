"""Immutable URI reference source for artifact content."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from mconet.core.domain.authorization import Authorization
from mconet.core.domain.open_identifier import OpenIdentifier
from mconet.core.domain.uri import UriValue

_URI_ARTIFACT_SOURCE_KIND = OpenIdentifier("artifact.uri")


@dataclass(frozen=True, slots=True)
class UriArtifactSource:
    """Describe artifact content by URI and optional opaque authorization.

    Construction preserves the URI reference exactly and retains authorization
    only for a later compatible handler. The value does not validate, resolve,
    fetch, download, open, or otherwise access the referenced content.
    """

    uri: UriValue
    """Absolute or relative URI reference retained without normalization."""

    authorization: Authorization | None = None
    """Optional opaque authorization retained for a later handler."""

    def __post_init__(self) -> None:
        """Require exact URI and optional authorization storage contracts."""
        uri = cast(object, self.uri)
        authorization = cast(object, self.authorization)

        # Construction verifies nominal storage only. URI syntax, absolute-form
        # requirements, and scheme policy remain visible to a later validator.
        if not isinstance(uri, UriValue):
            raise TypeError("UriArtifactSource uri must be a UriValue.")

        # Structural recognition checks only the public Authorization contract;
        # credentials stay opaque and are neither copied nor interpreted here.
        if authorization is not None and not isinstance(authorization, Authorization):
            raise TypeError(
                "UriArtifactSource authorization must be an Authorization or None."
            )

    @property
    def kind(self) -> OpenIdentifier:
        """Return the standard open identifier for URI artifact content."""
        # The shared identifier is immutable and classifies representation only;
        # returning it performs no URI resolution or external access.
        return _URI_ARTIFACT_SOURCE_KIND
