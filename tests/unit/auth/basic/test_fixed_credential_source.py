"""Tests for the fixed credential source."""

import asyncio
import pickle
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import cast

from mconet.auth.basic.fixed_credential_source import FixedCredentialSource
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

_PLACEHOLDER = "mconet-test-api-key-not-secret"


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
    """Concrete consumer permitted to reveal a fixed test secret."""


def _context(interaction_id: str) -> AuthorizationContext:
    """Build non-sensitive facts for one fixed-source resolution."""
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


def test_fixed_credential_source_stores_and_resolves_a_secret_value() -> None:
    """Verify every interaction reveals the same stored secret container."""
    secret = SecretValue(_PLACEHOLDER)
    source = FixedCredentialSource(secret)
    first = asyncio.run(source.resolve(_context("interaction-1")))
    second = asyncio.run(source.resolve(_context("interaction-2")))
    handler = _Handler()

    # Two resolutions return distinct wrappers around one SecretValue. The
    # plaintext is available only through an authorized consumer.
    assert isinstance(source, CredentialSource)
    assert isinstance(first, CredentialValue)
    assert isinstance(second, CredentialValue)
    assert first is not second
    assert first.kind == OpenIdentifier("credential.secret")
    assert first.reveal(handler) == _PLACEHOLDER
    assert second.reveal(handler) == first.reveal(handler)
    assert secret.reveal(handler) == _PLACEHOLDER


def test_fixed_credential_source_redacts_and_rejects_raw_storage() -> None:
    """Verify the secret cannot be stored as text or rendered from the source."""
    secret = SecretValue(_PLACEHOLDER)
    source = FixedCredentialSource(secret)
    credential = asyncio.run(source.resolve(_context("interaction-1")))

    # Redaction markers replace both the source and the returned credential.
    # A raw string is not an acceptable substitute for SecretValue.
    for rendered in (str(source), repr(source), str(credential), repr(credential)):
        assert _PLACEHOLDER not in rendered
        assert rendered == "[REDACTED]"
    _assert_raises(
        TypeError,
        lambda: FixedCredentialSource(cast(SecretValue, _PLACEHOLDER)),
        "secret must be a SecretValue",
    )
    _assert_raises(
        TypeError,
        lambda: asyncio.run(source.resolve(cast(AuthorizationContext, object()))),
        "context must be an AuthorizationContext",
    )
    _assert_raises(
        TypeError,
        lambda: credential.reveal(cast(AuthorizedSecretConsumer, object())),
        "consumer is not authorized",
    )


def test_fixed_credential_source_cannot_be_serialized() -> None:
    """Verify pickle cannot reconstruct the source or its credential."""
    source = FixedCredentialSource(SecretValue(_PLACEHOLDER))
    credential = asyncio.run(source.resolve(_context("interaction-1")))

    _assert_raises(TypeError, lambda: pickle.dumps(source), "cannot be serialized")
    _assert_raises(
        TypeError,
        lambda: pickle.dumps(credential),
        "cannot be serialized",
    )
