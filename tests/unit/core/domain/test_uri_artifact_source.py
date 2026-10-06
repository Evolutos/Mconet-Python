"""Tests for immutable URI artifact sources."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import FrozenInstanceError, dataclass
from typing import cast

from mconet.core.domain import (
    ArtifactSource,
    Authorization,
    OpenIdentifier,
    SecretValue,
    UriArtifactSource,
    UriValue,
)


@dataclass(frozen=True, slots=True)
class _Authorization:
    """Opaque test authorization retained without credential inspection."""

    kind: OpenIdentifier
    """Open identity used by a later authorization handler."""

    credential: SecretValue
    """Secret test value that the URI source must never inspect."""


@dataclass(frozen=True, slots=True)
class _MissingAuthorizationKind:
    """Credential holder intentionally missing the Authorization contract."""

    credential: SecretValue
    """Secret value that cannot substitute for authorization identity."""


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    # Keeping the exception boundary narrow prevents an unrelated setup failure
    # from satisfying a storage-contract assertion accidentally.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def _authorization() -> _Authorization:
    """Create one structurally valid authorization with an opaque credential."""
    # A fresh instance per call prevents identity assertions from depending on
    # shared fixture state while using a non-sensitive placeholder secret.
    return _Authorization(
        kind=OpenIdentifier("authorization.vendor_signature"),
        credential=SecretValue("placeholder-credential"),
    )


def test_uri_artifact_source_preserves_uri_and_authorization_identity() -> None:
    """Verify URI text and optional authorization are retained unchanged."""
    uri = UriValue(
        "HTTPS://content.example.test/a/../asset?q=%2f#Part",
        is_absolute=True,
    )
    authorization = _authorization()
    source = UriArtifactSource(uri, authorization)

    # No normalization, resolution, copying, or credential extraction occurs at
    # construction; later validators and handlers receive the original values.
    assert source.uri is uri
    assert source.uri.value == "HTTPS://content.example.test/a/../asset?q=%2f#Part"
    assert source.authorization is authorization
    assert str(authorization.credential) == "[REDACTED]"


def test_uri_artifact_source_allows_relative_uri_without_authorization() -> None:
    """Verify optional authorization and relative URI references stay explicit."""
    uri = UriValue("../artifacts/item.bin", is_absolute=False)
    source = UriArtifactSource(uri)

    # Relative references remain data for a later context-aware resolver, while
    # None means no authorization was attached rather than an implicit strategy.
    assert source.uri is uri
    assert source.authorization is None


def test_uri_artifact_source_has_standard_source_identity() -> None:
    """Verify the concrete value satisfies ArtifactSource with a stable kind."""
    first = UriArtifactSource(UriValue("https://example.test/a", True))
    second = UriArtifactSource(UriValue("https://example.test/b", True))

    # Source identity classifies representation and therefore does not depend on
    # URI text, reference form, authorization mechanism, or external reachability.
    assert isinstance(first, ArtifactSource)
    assert first.kind == OpenIdentifier("artifact.uri")
    assert second.kind == first.kind
    assert first.kind is second.kind


def test_uri_artifact_source_defers_uri_semantic_validation() -> None:
    """Verify construction preserves invalid syntax for the later validator."""
    uri = UriValue("missing-scheme", is_absolute=True)
    source = UriArtifactSource(uri)

    # Definition owns field shape only. Calling validate_uri here would collapse
    # construction and validation phases and prevent aggregate Artifact checks.
    assert source.uri is uri
    assert source.uri.value == "missing-scheme"
    assert source.uri.is_absolute is True


def test_uri_artifact_source_is_frozen_and_performs_no_access() -> None:
    """Verify the source is immutable and exposes no content-access behavior."""
    source = UriArtifactSource(UriValue("https://example.test/asset", True))
    parameters = inspect.signature(UriArtifactSource).parameters

    # Exact constructor shape retains only reference data. Explicit absence
    # checks prevent convenience methods from introducing hidden network I/O.
    assert tuple(parameters) == ("uri", "authorization")
    assert parameters["authorization"].default is None
    for operation in ("read", "open", "fetch", "download", "resolve", "stream"):
        assert not hasattr(source, operation)
    _assert_raises(
        FrozenInstanceError,
        lambda: source.__setattr__(
            "uri", UriValue("https://example.test/replacement", True)
        ),
        "cannot assign to field",
    )


def test_uri_artifact_source_rejects_invalid_storage_types() -> None:
    """Verify dynamic callers cannot bypass URI and authorization contracts."""
    missing_kind = _MissingAuthorizationKind(SecretValue("placeholder-credential"))

    # Each failure is attributed to its own field boundary; no fallback treats a
    # string as a URI or an arbitrary credential holder as Authorization.
    _assert_raises(
        TypeError,
        lambda: UriArtifactSource(cast(UriValue, "https://example.test/asset")),
        "uri must be a UriValue",
    )
    _assert_raises(
        TypeError,
        lambda: UriArtifactSource(
            UriValue("https://example.test/asset", True),
            cast(Authorization, missing_kind),
        ),
        "authorization must be an Authorization or None",
    )
