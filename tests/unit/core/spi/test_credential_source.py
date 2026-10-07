"""Structural and lifecycle tests for the asynchronous credential source contract."""

from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass, field
from typing import Never, SupportsIndex, cast, get_type_hints

from mconet.core.domain import (
    AuthorizedSecretConsumer,
    Extensions,
    ModelDescriptor,
    ModelTarget,
    NamedModel,
    OpenIdentifier,
    SecretValue,
    Timestamp,
    UriValue,
)
from mconet.core.spi import (
    AuthorizationContext,
    BodySigningMode,
    CredentialSource,
    CredentialValue,
)

_REDACTED_TEXT = "[REDACTED]"


def _empty_extensions() -> Extensions:
    """Create independent portable storage for target fixtures."""
    # Fresh storage prevents source tests from sharing mutable target extension
    # membership before AuthorizationContext takes its immutable snapshot.
    return {}


@dataclass(frozen=True, slots=True)
class _Target:
    """Complete structural model target used by source contexts."""

    service_id: OpenIdentifier
    """Open model-service identity."""

    protocol_id: OpenIdentifier
    """Open interaction-protocol identity."""

    model: ModelDescriptor
    """Exact model descriptor selected for the interaction."""

    deployment_id: str | None = None
    """Optional service deployment identity."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Portable target fields retained for future integrations."""


class _Credential:
    """Secure ordinary credential value returned by source fixtures."""

    __slots__ = ("_kind", "_secret")

    def __init__(self, kind: OpenIdentifier, secret: SecretValue) -> None:
        """Store non-sensitive kind metadata and protected secret storage."""
        # Plaintext remains inside SecretValue; constructing a source result does
        # not reveal, copy, format, or serialize it.
        self._kind = kind
        self._secret = secret

    @property
    def kind(self) -> OpenIdentifier:
        """Return the non-sensitive open credential discriminator."""
        # Source callers may observe shape without reading the protected value.
        return self._kind

    def reveal(self, consumer: AuthorizedSecretConsumer) -> object:
        """Delegate plaintext access to the nominal SecretValue boundary."""
        # SecretValue validates the selected authorization handler before
        # returning exact protected data.
        return self._secret.reveal(consumer)

    def __str__(self) -> str:
        """Return a fixed safe marker for ordinary text conversion."""
        # Provider, token, and account properties cannot enter logs through str.
        return _REDACTED_TEXT

    def __repr__(self) -> str:
        """Return the same fixed marker used by containers and logging."""
        # Container rendering therefore cannot inspect protected source results.
        return _REDACTED_TEXT

    def __getstate__(self) -> Never:
        """Reject state serialization before protected slots are inspected."""
        # Credential persistence requires an application-specific secure protocol.
        raise TypeError("CredentialValue cannot be serialized.")

    def __reduce_ex__(self, protocol: SupportsIndex) -> Never:
        """Reject pickle and copy reconstruction protocols."""
        # No protocol version may select a weaker serialization path.
        del protocol
        raise TypeError("CredentialValue cannot be serialized.")


class _SequenceSource:
    """Ordinary source returning one configured credential per invocation."""

    def __init__(self, credentials: tuple[CredentialValue, ...]) -> None:
        """Store an ordered finite sequence and initialize the call record."""
        # Separate objects make accidental SDK caching observable across two
        # interactions without introducing a provider-specific refresh policy.
        self._credentials = credentials
        self.calls: list[AuthorizationContext] = []

    async def resolve(self, context: AuthorizationContext) -> CredentialValue:
        """Record one interaction and return its next configured credential."""
        # Yield once to exercise a genuine async provider boundary before using
        # the current invocation index to select a fresh configured result.
        await asyncio.sleep(0)
        index = len(self.calls)
        self.calls.append(context)
        return self._credentials[index]


class _SourceFailure(RuntimeError):
    """Represent one exact provider failure in source contract tests."""


class _FailingSource:
    """Ordinary source that propagates one configured asynchronous failure."""

    def __init__(self, failure: _SourceFailure) -> None:
        """Store the exact failure produced by the provider boundary."""
        # Exception identity lets the test detect wrapping, retries, or fallback.
        self.failure = failure

    async def resolve(self, context: AuthorizationContext) -> CredentialValue:
        """Raise the configured failure without returning a partial credential."""
        # The complete context is accepted but contains no plaintext to recover
        # or publish when the external provider operation fails.
        del context
        raise self.failure


class _IncompleteSource:
    """Source-shaped fixture intentionally missing asynchronous resolution."""


def _target() -> _Target:
    """Build one valid structural target for authorization context fixtures."""
    # NamedModel uses the production descriptor path so semantic context
    # validation remains active instead of relying on a loose cast-only mock.
    return _Target(
        service_id=OpenIdentifier("service.example"),
        protocol_id=OpenIdentifier("protocol.example"),
        model=NamedModel("model-example"),
        deployment_id="deployment-a",
        extensions={"provider.region": "test-region"},
    )


def _context(interaction_id: str) -> AuthorizationContext:
    """Build complete immutable non-sensitive facts for one source invocation."""
    # Distinct IDs make per-interaction calls observable while every other fact
    # stays stable and free of authorization payload or credential material.
    return AuthorizationContext(
        interaction_id=interaction_id,
        target=cast(ModelTarget, _target()),
        endpoint=UriValue("https://models.example.test/v1", True),
        transport_kind=OpenIdentifier("http"),
        timestamp=Timestamp(1_800_000_000, 123_456_789),
        body_signing_mode=cast(BodySigningMode, "none"),
        extensions={"authorization.region": "east"},
    )


def _credential(identifier: str) -> _Credential:
    """Build one protected credential with a non-sensitive test identity."""
    # The identifier contributes only to a recognized placeholder and is never
    # printed or serialized through the returned CredentialValue.
    return _Credential(
        OpenIdentifier("credential.bearer"),
        SecretValue(f"placeholder-source-value-{identifier}"),
    )


def _accept_source(source: CredentialSource) -> CredentialSource:
    """Return a source after crossing the statically checked protocol boundary."""
    # Pyright verifies the ordinary async implementation without inheritance,
    # registration, cache interfaces, or provider-specific dependencies.
    return source


def test_credential_source_accepts_ordinary_structural_class() -> None:
    """Require only the documented asynchronous resolution operation."""
    source = _SequenceSource((_credential("first"),))

    accepted = _accept_source(source)

    # Static and runtime conformance agree without an SDK base class, component
    # descriptor, registry ID, refresh API, or persistence representation.
    assert accepted is source
    assert isinstance(source, CredentialSource)


def test_credential_source_resolves_once_for_each_interaction() -> None:
    """Invoke the provider independently and preserve each returned credential."""
    first = _credential("first")
    second = _credential("second")
    first_context = _context("interaction-1")
    second_context = _context("interaction-2")
    source = _SequenceSource((first, second))

    first_result = asyncio.run(source.resolve(first_context))
    second_result = asyncio.run(source.resolve(second_context))

    # Two provider calls with exact contexts and distinct outputs prove Runtime
    # cannot cache the first CredentialValue across authorization interactions.
    assert source.calls == [first_context, second_context]
    assert source.calls[0] is first_context
    assert source.calls[1] is second_context
    assert first_result is first
    assert second_result is second
    assert first_result is not second_result


def test_credential_source_propagates_failure_without_partial_value() -> None:
    """Preserve the exact asynchronous provider failure and return no fallback."""
    failure = _SourceFailure("provider unavailable")
    source = _FailingSource(failure)

    try:
        asyncio.run(source.resolve(_context("interaction-failure")))
    except _SourceFailure as error:
        # Exact identity proves the contract layer neither retries nor replaces
        # the failure with a cached, empty, or otherwise fabricated credential.
        assert error is failure
    else:
        raise AssertionError("Expected credential source failure to be raised.")


def test_credential_source_has_exact_asynchronous_method_surface() -> None:
    """Lock the method name, context input, result, and asynchronous semantics."""
    method = CredentialSource.resolve
    annotations = get_type_hints(method)

    # The sole input contains non-sensitive interaction facts; no authorization
    # object, mutable request, plaintext, cache, retry, or persistence API leaks in.
    assert tuple(inspect.signature(method).parameters) == ("self", "context")
    assert annotations == {
        "context": AuthorizationContext,
        "return": CredentialValue,
    }
    assert inspect.iscoroutinefunction(method)


def test_credential_source_requires_complete_behavior_surface() -> None:
    """Reject an object without the asynchronous resolve operation."""
    incomplete = _IncompleteSource()

    # A source has no metadata-only substitute; resolution itself is mandatory.
    assert not isinstance(incomplete, CredentialSource)


def test_credential_source_exposes_no_sdk_owned_provider_policy() -> None:
    """Keep caching, refresh, retry, persistence, and registries out of the SPI."""
    source = _SequenceSource((_credential("only"),))

    # Applications may implement private provider policy, but the shared SDK
    # contract cannot require or invoke these lifecycle and storage operations.
    for forbidden_member in (
        "cache",
        "refresh",
        "retry",
        "persist",
        "serialize",
        "register",
        "reveal",
    ):
        assert not hasattr(source, forbidden_member)
