"""Tests for applying one authorization handler."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import cast

from mconet.core.domain import (
    Authorization,
    Bytes,
    HeaderField,
    Headers,
    MediaType,
    ModelInteractionError,
    ModelTarget,
    NamedModel,
    OpenIdentifier,
    QueryParameters,
    Timestamp,
    UriValue,
)
from mconet.core.runtime._authorization_application import apply_authorization_handler
from mconet.core.spi import (
    AuthorizationContext,
    AuthorizationHandler,
    BodySigningMode,
    ComponentDescriptor,
    MutableTransportRequest,
    ResolvedAuthorizationHandler,
    TransportBody,
)


def _capture(action: Callable[[], object]) -> BaseException:
    """Run one action and return the exception it raises."""
    try:
        action()
    except BaseException as error:
        return error
    raise AssertionError("Expected the action to fail.")


class _Target:
    """Structural model target for one authorization context."""

    def __init__(self) -> None:
        """Store the minimum target fields."""
        self.service_id = OpenIdentifier("service.example")
        self.protocol_id = OpenIdentifier("protocol.example")
        self.model = NamedModel("model-example")
        self.deployment_id = None
        self.extensions: dict[str, str] = {}


class _Authorization:
    """Opaque decision with no credential payload."""

    def __init__(self) -> None:
        """Store the handler discriminator."""
        self.kind = OpenIdentifier("authorization.none")


class _Handler:
    """Handler that replaces headers and records the application."""

    def __init__(self, headers: Headers) -> None:
        """Store the headers written by ``apply``."""
        self.descriptor = ComponentDescriptor("handler", "1.0.0", "application")
        self._headers = headers
        self.apply_calls = 0

    def supports(self, *values: object) -> frozenset[str]:
        """Report the no-signing mode without being called by this stage."""
        del values
        return frozenset(("none",))

    async def apply(
        self,
        authorization: Authorization,
        context: AuthorizationContext,
        request: MutableTransportRequest,
    ) -> None:
        """Replace headers once."""
        del authorization, context
        self.apply_calls += 1
        request.replace_headers(self._headers)


class _Transport:
    """Transport that application must not use."""

    def __init__(self) -> None:
        """Store an empty call list."""
        self.calls: list[str] = []

    async def send(self, *values: object) -> object:
        """Record a send."""
        del values
        self.calls.append("send")
        return object()


def _context() -> AuthorizationContext:
    """Return non-sensitive facts for one application."""
    return AuthorizationContext(
        interaction_id="interaction-1",
        target=cast(ModelTarget, _Target()),
        endpoint=UriValue("https://models.example.test/v1", True),
        transport_kind=OpenIdentifier("http"),
        timestamp=Timestamp(1_700_000_000, 0),
        body_signing_mode=cast(BodySigningMode, "none"),
    )


def _request() -> MutableTransportRequest:
    """Return an open request with one ordinary header."""
    return MutableTransportRequest(
        method="POST",
        url=UriValue("https://models.example.test/v1/chat/completions", True),
        headers=Headers((HeaderField("X-Trace", "trace"),)),
        query=QueryParameters(),
        body=TransportBody(Bytes(b"{}"), MediaType("application", "json")),
    )


def _resolved(handler: _Handler) -> ResolvedAuthorizationHandler:
    """Bind the handler to the no-signing mode."""
    return ResolvedAuthorizationHandler(
        cast(AuthorizationHandler, handler),
        cast(BodySigningMode, "none"),
    )


def test_apply_changes_only_the_open_request_and_checks_headers() -> None:
    """Verify a legal header is kept and an illegal header fails before send."""
    transport = _Transport()
    legal = _Handler(Headers((HeaderField("X-Trace", "trace"),)))
    applied = asyncio.run(
        apply_authorization_handler(
            _resolved(legal),
            _Authorization(),
            _context(),
            _request(),
        )
    )
    illegal_name = _capture(
        lambda: asyncio.run(
            apply_authorization_handler(
                _resolved(_Handler(Headers((HeaderField("Bad Name", "trace"),)))),
                _Authorization(),
                _context(),
                _request(),
            )
        )
    )
    illegal_value = _capture(
        lambda: asyncio.run(
            apply_authorization_handler(
                _resolved(_Handler(Headers((HeaderField("X-Trace", "a\nb"),)))),
                _Authorization(),
                _context(),
                _request(),
            )
        )
    )

    assert legal.apply_calls == 1
    assert applied.headers.values[0].name == "X-Trace"
    assert isinstance(illegal_name, ModelInteractionError)
    assert illegal_name.code == "invalid_authorization_header_name"
    assert isinstance(illegal_value, ModelInteractionError)
    assert illegal_value.code == "invalid_authorization_header_value"
    assert transport.calls == []
