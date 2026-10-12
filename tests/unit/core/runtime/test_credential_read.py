"""Tests that a credential read failure does not continue authorization."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import cast

from mconet.core.domain import (
    Authorization,
    ModelInteractionError,
    ModelTarget,
    NamedModel,
    OpenIdentifier,
    Timestamp,
    UriValue,
)
from mconet.core.domain.error_category import ErrorCategory
from mconet.core.domain.interaction_phase import InteractionPhase
from mconet.core.runtime._credential_read import read_interaction_credential
from mconet.core.spi import (
    AuthorizationContext,
    BodySigningMode,
    CredentialSource,
    CredentialValue,
)


def _capture(action: Callable[[], object]) -> BaseException:
    """Run one action and return the exception it raises."""
    try:
        action()
    except BaseException as error:
        return error
    raise AssertionError("Expected the action to fail.")


class _Target:
    """Structural model target accepted by authorization context validation."""

    def __init__(self) -> None:
        """Store the minimum target fields."""
        self.service_id = OpenIdentifier("service.example")
        self.protocol_id = OpenIdentifier("protocol.example")
        self.model = NamedModel("model-example")
        self.deployment_id = None
        self.extensions: dict[str, str] = {}


class _Authorization:
    """Decision that owns one credential source."""

    def __init__(self, source: object) -> None:
        """Store the discriminator and source."""
        self.kind = OpenIdentifier("authorization.bearer")
        self.credential_source = source


class _NoSource:
    """Decision that does not own a credential source."""

    def __init__(self) -> None:
        """Store only the discriminator."""
        self.kind = OpenIdentifier("authorization.none")


class _Source:
    """Source that fails once and records the call."""

    def __init__(self, error: BaseException) -> None:
        """Store the failure returned by ``resolve``."""
        self.error = error
        self.calls = 0

    async def resolve(self, context: AuthorizationContext) -> CredentialValue:
        """Record one read and raise the prepared failure."""
        del context
        self.calls += 1
        raise self.error


class _Handler:
    """Handler that a failed read must not apply."""

    def __init__(self) -> None:
        """Store an empty application count."""
        self.apply_calls = 0

    async def apply(self, *values: object) -> None:
        """Record an application."""
        del values
        self.apply_calls += 1


class _Transport:
    """Transport that a failed read must not use."""

    def __init__(self) -> None:
        """Store an empty call list."""
        self.calls: list[str] = []

    async def send(self, *values: object) -> object:
        """Record a send."""
        del values
        self.calls.append("send")
        return object()


def _context() -> AuthorizationContext:
    """Return non-sensitive facts for one credential read."""
    return AuthorizationContext(
        interaction_id="interaction-1",
        target=cast(ModelTarget, _Target()),
        endpoint=UriValue("https://models.example.test/v1", True),
        transport_kind=OpenIdentifier("http"),
        timestamp=Timestamp(1_700_000_000, 0),
        body_signing_mode=cast(BodySigningMode, "none"),
    )


def test_credential_failure_does_not_apply_or_send() -> None:
    """Verify one source failure is not retried and later stages stay idle."""
    failure = ModelInteractionError(
        ErrorCategory(OpenIdentifier("authentication")),
        InteractionPhase(OpenIdentifier("credential_resolution")),
        "credential_unavailable",
        "The credential could not be read.",
    )
    source = _Source(failure)
    handler = _Handler()
    transport = _Transport()
    error = _capture(
        lambda: asyncio.run(
            read_interaction_credential(
                cast(Authorization, _Authorization(cast(CredentialSource, source))),
                _context(),
            )
        )
    )

    assert error is failure
    assert source.calls == 1
    assert handler.apply_calls == 0
    assert transport.calls == []


def test_missing_source_returns_none() -> None:
    """Verify a decision without a source does not invent a credential."""
    credential = asyncio.run(
        read_interaction_credential(cast(Authorization, _NoSource()), _context())
    )

    assert credential is None
