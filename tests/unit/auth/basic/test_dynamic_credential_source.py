"""Tests for the dynamic credential source."""

import asyncio
import pickle
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import cast

from mconet.auth.basic.dynamic_credential_source import DynamicCredentialSource
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
from mconet.core.spi import AuthorizationContext, BodySigningMode, CredentialSource

_FIRST = "mconet-test-api-key-not-secret"
_SECOND = "mconet-test-bearer-token-not-secret"


def _empty_extensions() -> Extensions:
    """Create independent extension storage for one target fixture."""
    return {}


@dataclass(frozen=True, slots=True)
class _Target:
    """Complete structural model target for one authorization context."""

    service_id: OpenIdentifier
    protocol_id: OpenIdentifier
    model: ModelDescriptor
    deployment_id: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


class _Handler(AuthorizedSecretConsumer):
    """Concrete consumer permitted to reveal a dynamic test secret."""


class _Provider:
    """Async provider that returns a new secret for each recorded context."""

    def __init__(self, secrets: tuple[str, ...]) -> None:
        """Store the secrets that successive resolutions should observe."""
        self._secrets = secrets
        self.calls: list[AuthorizationContext] = []

    async def __call__(self, context: AuthorizationContext) -> SecretValue:
        """Record the context and return the next secret container."""
        index = len(self.calls)
        self.calls.append(context)
        return SecretValue(self._secrets[index])


def _context(interaction_id: str) -> AuthorizationContext:
    """Build non-sensitive facts for one dynamic resolution."""
    return AuthorizationContext(
        interaction_id=interaction_id,
        target=cast(
            ModelTarget,
            _Target(
                OpenIdentifier("service.example"),
                OpenIdentifier("protocol.example"),
                NamedModel("model-example"),
            ),
        ),
        endpoint=UriValue("https://models.example.test/v1", True),
        transport_kind=OpenIdentifier("http"),
        timestamp=Timestamp(1_800_000_000, 0),
        body_signing_mode=cast(BodySigningMode, "none"),
    )


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> BaseException:
    """Require an action to raise the expected exception and message fragment."""
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return error
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_dynamic_credential_source_calls_the_provider_for_every_resolve() -> None:
    """Verify a later interaction cannot reuse the previous secret."""
    provider = _Provider((_FIRST, _SECOND))
    source = DynamicCredentialSource(provider)
    first_context = _context("interaction-1")
    second_context = _context("interaction-2")

    # Construction retains the provider without asking it for a secret.
    assert provider.calls == []
    first = asyncio.run(source.resolve(first_context))
    second = asyncio.run(source.resolve(second_context))
    handler = _Handler()

    assert isinstance(source, CredentialSource)
    assert provider.calls == [first_context, second_context]
    assert first.reveal(handler) == _FIRST
    assert second.reveal(handler) == _SECOND
    assert _FIRST not in repr(source)
    assert _SECOND not in repr(second)


def test_dynamic_credential_source_propagates_provider_failure() -> None:
    """Verify a failed call does not substitute an earlier secret."""

    class _FailingProvider:
        """Provider that succeeds once and then raises its own error."""

        def __init__(self) -> None:
            self.calls = 0
            self.failure = RuntimeError("provider unavailable")

        async def __call__(self, context: AuthorizationContext) -> SecretValue:
            del context
            self.calls += 1
            if self.calls == 1:
                return SecretValue(_FIRST)
            raise self.failure

    provider = _FailingProvider()
    source = DynamicCredentialSource(provider)
    handler = _Handler()
    first = asyncio.run(source.resolve(_context("interaction-1")))

    try:
        asyncio.run(source.resolve(_context("interaction-2")))
    except RuntimeError as error:
        assert error is provider.failure
    else:
        raise AssertionError("Expected the provider failure to propagate.")

    # The first credential remains usable, and the failure is not replaced.
    assert first.reveal(handler) == _FIRST
    assert provider.calls == 2
    assert _FIRST not in str(provider.failure)


def test_dynamic_credential_source_rejects_sync_providers_and_raw_results() -> None:
    """Verify only an async provider result stored as a secret is accepted."""

    def sync_provider(context: AuthorizationContext) -> SecretValue:
        del context
        return SecretValue(_FIRST)

    async def raw_provider(context: AuthorizationContext) -> str:
        del context
        return _FIRST

    construct = cast(Callable[..., DynamicCredentialSource], DynamicCredentialSource)
    _assert_raises(
        TypeError,
        lambda: construct(sync_provider),
        "provider must be asynchronous",
    )
    source = construct(raw_provider)
    error = _assert_raises(
        TypeError,
        lambda: asyncio.run(source.resolve(_context("interaction-1"))),
        "provider must return a SecretValue",
    )
    assert _FIRST not in str(error)


def test_dynamic_credential_source_cannot_be_serialized() -> None:
    """Verify pickle cannot reconstruct the provider or a returned credential."""
    source = DynamicCredentialSource(_Provider((_FIRST,)))
    credential = asyncio.run(source.resolve(_context("interaction-1")))

    _assert_raises(TypeError, lambda: pickle.dumps(source), "cannot be serialized")
    _assert_raises(TypeError, lambda: pickle.dumps(credential), "cannot be serialized")
