"""Structural, security, and mutation tests for authorization handlers."""

from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass, field
from typing import Self, cast, get_type_hints

from mconet.core.domain import (
    Authorization,
    AuthorizedSecretConsumer,
    Bytes,
    Extensions,
    HeaderField,
    Headers,
    MediaType,
    ModelDescriptor,
    ModelTarget,
    NamedModel,
    OpenIdentifier,
    QueryParameters,
    SecretValue,
    Timestamp,
    UriValue,
)
from mconet.core.spi import (
    AuthorizationContext,
    AuthorizationHandler,
    BodySigningMode,
    BodySigningRequirement,
    ComponentDescriptor,
    MutableTransportRequest,
    TransportBody,
)


def _empty_extensions() -> Extensions:
    """Create independent portable extension storage for target fixtures."""
    # Fresh mappings prevent two structural targets from sharing mutable input
    # before AuthorizationContext creates its read-only snapshot.
    return {}


@dataclass(frozen=True, slots=True)
class _Target:
    """Complete structural model target for authorization context fixtures."""

    service_id: OpenIdentifier
    """Open model-service identity."""

    protocol_id: OpenIdentifier
    """Open protocol identity."""

    model: ModelDescriptor
    """Exact model descriptor selected before authorization."""

    deployment_id: str | None = None
    """Optional provider deployment identity."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Portable non-sensitive target facts."""


class _TrackingSecret(SecretValue):
    """Test secret recording only successful reveal attempts."""

    __slots__ = ("_reveal_count",)

    def __init__(self, value: str) -> None:
        """Store protected text and initialize the private reveal counter."""
        # Base construction keeps plaintext behind SecretValue while direct slot
        # initialization avoids weakening its public immutability guard.
        super().__init__(value)
        object.__setattr__(self, "_reveal_count", 0)

    @property
    def reveal_count(self) -> int:
        """Return how many authorized plaintext reads occurred in the fixture."""
        # The counter contains no secret and is exposed only to prove capability
        # matching never consumes credentials before handler selection.
        return cast(int, object.__getattribute__(self, "_reveal_count"))

    def reveal(self, consumer: AuthorizedSecretConsumer) -> str | Bytes:
        """Record an authorized attempt and delegate the nominal access check."""
        # Delegate first so rejected consumers never count as successful reads;
        # successful apply then has one observable read and supports has none.
        value = super().reveal(consumer)
        object.__setattr__(self, "_reveal_count", self.reveal_count + 1)
        return value


@dataclass(frozen=True, slots=True)
class _BearerAuthorization:
    """Opaque bearer authorization fixture owning one protected token."""

    kind: OpenIdentifier
    """Non-sensitive handler-selection discriminator."""

    token: _TrackingSecret
    """Protected token available only through an authorized consumer."""


class _BearerHandler(AuthorizedSecretConsumer):
    """Ordinary handler that applies one bearer header inside the open window."""

    def __new__(
        cls,
        descriptor: ComponentDescriptor,
        supported_modes: frozenset[BodySigningMode],
    ) -> Self:
        """Create a nominal consumer with the same public constructor surface."""
        # AuthorizedSecretConsumer owns only the nominal capability check; the
        # matching arguments are initialized by this concrete handler below.
        del descriptor, supported_modes
        return super().__new__(cls)

    def __init__(
        self,
        descriptor: ComponentDescriptor,
        supported_modes: frozenset[BodySigningMode],
    ) -> None:
        """Store metadata, supported modes, and empty operation records."""
        # Handler-local immutable capability facts keep supports deterministic;
        # call records expose exact input identities without external effects.
        self.descriptor = descriptor
        self._supported_modes = supported_modes
        self.support_calls: list[tuple[Authorization, BodySigningRequirement]] = []
        self.apply_calls: list[
            tuple[Authorization, AuthorizationContext, MutableTransportRequest]
        ] = []

    def supports(
        self,
        authorization: Authorization,
        body_signing_requirement: BodySigningRequirement,
    ) -> frozenset[BodySigningMode]:
        """Return compatible modes without reading the bearer token."""
        # Record only opaque inputs, then preserve protocol preference membership
        # while returning immutable set semantics to the resolver.
        self.support_calls.append((authorization, body_signing_requirement))
        if not isinstance(authorization, _BearerAuthorization):
            return frozenset()
        return frozenset(
            mode
            for mode in body_signing_requirement.acceptable_modes
            if mode in self._supported_modes
        )

    async def apply(
        self,
        authorization: Authorization,
        context: AuthorizationContext,
        request: MutableTransportRequest,
    ) -> None:
        """Reveal one token and append its bearer header to the open request."""
        # Validate the selected opaque type and signing decision before accessing
        # protected data, so a mismatched invocation cannot consume a credential.
        if not isinstance(authorization, _BearerAuthorization):
            raise TypeError("Bearer handler requires bearer authorization.")
        if context.body_signing_mode not in self._supported_modes:
            raise ValueError("Bearer handler received an unsupported signing mode.")
        if request.is_frozen:
            raise RuntimeError("Bearer handler requires an open request.")

        # Yield at the credential boundary without performing network I/O, then
        # use nominal consumer access and one whole-value header replacement.
        await asyncio.sleep(0)
        token = authorization.token.reveal(self)
        if not isinstance(token, str):
            raise TypeError("Bearer handler requires a string token.")
        request.replace_headers(
            Headers(
                (
                    *request.headers.values,
                    HeaderField("Authorization", f"Bearer {token}"),
                )
            )
        )
        self.apply_calls.append((authorization, context, request))


class _FailingHandler(AuthorizedSecretConsumer):
    """Complete handler propagating one configured authorization failure."""

    descriptor = ComponentDescriptor("Failing handler", "1.0.0", "application")
    """Valid metadata isolates the asynchronous apply failure."""

    def __new__(cls, failure: RuntimeError) -> Self:
        """Create a nominal consumer with the configured constructor surface."""
        # The marker validates the concrete subclass; __init__ retains the exact
        # failure after allocation without giving the base class mutable state.
        del failure
        return super().__new__(cls)

    def __init__(self, failure: RuntimeError) -> None:
        """Store the exact failure produced inside the authorization window."""
        # Exception identity exposes wrapping, retries, fallback, or freezing.
        self.failure = failure

    def supports(
        self,
        authorization: Authorization,
        body_signing_requirement: BodySigningRequirement,
    ) -> frozenset[BodySigningMode]:
        """Report canonical no-signing support without consuming credentials."""
        # Inputs are opaque selection facts; this configured fixture supports the
        # canonical mode without inspecting provider-specific fields.
        del authorization, body_signing_requirement
        return frozenset(("none",))

    async def apply(
        self,
        authorization: Authorization,
        context: AuthorizationContext,
        request: MutableTransportRequest,
    ) -> None:
        """Raise the configured failure without changing or freezing the request."""
        # Accept complete apply inputs but produce no partial authorization state.
        del authorization, context, request
        raise self.failure


class _UnmarkedHandler:
    """Structurally complete handler without nominal secret-read capability."""

    descriptor = ComponentDescriptor("Unmarked handler", "1.0.0", "application")
    """Valid metadata permits structural handler conformance."""

    def supports(
        self,
        authorization: Authorization,
        body_signing_requirement: BodySigningRequirement,
    ) -> frozenset[BodySigningMode]:
        """Report no compatible modes without inspecting secret fields."""
        # Structural behavior alone does not opt into protected-value access.
        del authorization, body_signing_requirement
        return frozenset()

    async def apply(
        self,
        authorization: Authorization,
        context: AuthorizationContext,
        request: MutableTransportRequest,
    ) -> None:
        """Accept inputs without mutation for nominal-boundary verification."""
        # This no-op remains a valid non-secret handler implementation, but it
        # cannot pass itself to SecretValue.reveal.
        del authorization, context, request


class _IncompleteHandler:
    """Component-shaped fixture intentionally missing handler operations."""

    descriptor = ComponentDescriptor("Incomplete", "1.0.0", "application")
    """Valid metadata isolates the absent supports and apply methods."""


def _handler() -> _BearerHandler:
    """Build one bearer handler supporting the canonical no-signing mode."""
    # The descriptor is a real production value so structural conformance also
    # exercises the nominal metadata boundary used by Runtime components.
    return _BearerHandler(
        ComponentDescriptor("Bearer handler", "1.0.0", "application"),
        frozenset(("none",)),
    )


def _authorization() -> _BearerAuthorization:
    """Build one opaque bearer authorization with a protected placeholder."""
    # The recognized test placeholder exercises reveal and mutation without
    # introducing a real credential into source, logs, or snapshots.
    return _BearerAuthorization(
        OpenIdentifier("authorization.bearer"),
        _TrackingSecret("redacted-test-value"),
    )


def _context() -> AuthorizationContext:
    """Build complete non-sensitive facts for one authorization invocation."""
    # Runtime-selected mode and stable time enter explicitly; the handler does
    # not choose a mode, sample a clock, or recover request data from extensions.
    target = _Target(
        OpenIdentifier("service.example"),
        OpenIdentifier("protocol.example"),
        NamedModel("model-example"),
    )
    return AuthorizationContext(
        interaction_id="interaction-1",
        target=cast(ModelTarget, target),
        endpoint=UriValue("https://models.example.test/v1", True),
        transport_kind=OpenIdentifier("http"),
        timestamp=Timestamp(1_800_000_000, 123_456_789),
        body_signing_mode="none",
    )


def _request() -> MutableTransportRequest:
    """Build one encoded request with an open authorization window."""
    # Existing protocol fields make it observable that apply changes only the
    # authorized header collection while retaining method, URL, query, and body.
    return MutableTransportRequest(
        method="POST",
        url=UriValue("https://models.example.test/v1/run", True),
        headers=Headers((HeaderField("X-Trace", "trace-value"),)),
        query=QueryParameters(),
        body=TransportBody(
            Bytes(b'{"input":"hello"}'),
            MediaType("application", "json"),
        ),
    )


def _accept_handler(handler: AuthorizationHandler) -> AuthorizationHandler:
    """Return a handler after crossing the statically checked protocol boundary."""
    # Pyright verifies ordinary behavior without registry membership, component
    # IDs, one provider base class, or a transport dependency.
    return handler


def test_authorization_handler_accepts_structural_implementation() -> None:
    """Require metadata plus matching and asynchronous application behavior."""
    handler = _handler()

    accepted = _accept_handler(handler)

    # Static and runtime conformance agree for a concrete nominal secret consumer.
    assert accepted is handler
    assert isinstance(handler, AuthorizationHandler)
    assert handler.descriptor.name == "Bearer handler"


def test_authorization_handler_supports_without_revealing_or_mutating() -> None:
    """Match opaque authorization and signing facts without side effects."""
    handler = _handler()
    authorization = _authorization()
    requirement = BodySigningRequirement()
    request = _request()
    original_values = (request.url, request.headers, request.query, request.body)

    modes = handler.supports(authorization, requirement)

    # Matching returns immutable compatibility facts while the protected token,
    # request window, and asynchronous apply record remain untouched.
    assert modes == frozenset(("none",))
    assert handler.support_calls == [(authorization, requirement)]
    assert handler.support_calls[0][0] is authorization
    assert handler.support_calls[0][1] is requirement
    assert authorization.token.reveal_count == 0
    assert (
        request.url,
        request.headers,
        request.query,
        request.body,
    ) == original_values
    assert handler.apply_calls == []


def test_authorization_handler_applies_only_inside_open_request_window() -> None:
    """Consume one credential and mutate the selected request without freezing."""
    handler = _handler()
    authorization = _authorization()
    context = _context()
    request = _request()
    original_values = (request.method, request.url, request.query, request.body)

    result = asyncio.run(handler.apply(authorization, context, request))

    # Apply returns no alternate request, preserves non-header values, appends
    # exactly one authorization field, and leaves freezing to Runtime.
    assert result is None
    assert authorization.token.reveal_count == 1
    assert request.headers.get_all("Authorization") == ("Bearer redacted-test-value",)
    assert (request.method, request.url, request.query, request.body) == original_values
    assert request.is_frozen is False
    assert handler.apply_calls == [(authorization, context, request)]
    assert handler.apply_calls[0][0] is authorization
    assert handler.apply_calls[0][1] is context
    assert handler.apply_calls[0][2] is request


def test_authorization_handler_propagates_failure_without_request_change() -> None:
    """Preserve an apply failure and leave the authorization window open."""
    failure = RuntimeError("credential provider failed")
    handler = _FailingHandler(failure)
    authorization = _authorization()
    context = _context()
    request = _request()
    original_values = (request.url, request.headers, request.query, request.body)

    try:
        asyncio.run(handler.apply(authorization, context, request))
    except RuntimeError as error:
        # Exact identity proves the abstract boundary neither wraps the error nor
        # freezes, sends, or invents a partially authorized fallback request.
        assert error is failure
    else:
        raise AssertionError("Expected authorization application failure.")
    assert (
        request.url,
        request.headers,
        request.query,
        request.body,
    ) == original_values
    assert request.is_frozen is False


def test_authorization_handler_requires_nominal_secret_capability() -> None:
    """Keep structural conformance separate from protected-value authorization."""
    handler = _UnmarkedHandler()
    secret = SecretValue("redacted-test-value")

    # A handler may need no credential and remain structurally valid, but only an
    # explicit AuthorizedSecretConsumer subclass can reveal protected plaintext.
    assert isinstance(handler, AuthorizationHandler)
    try:
        secret.reveal(cast(AuthorizedSecretConsumer, handler))
    except TypeError as error:
        assert "consumer is not authorized" in str(error)
    else:
        raise AssertionError("Expected nominal secret consumer rejection.")


def test_authorization_handler_has_exact_method_surface() -> None:
    """Lock matching inputs, immutable modes, apply inputs, and async semantics."""
    supports = AuthorizationHandler.supports
    apply = AuthorizationHandler.apply

    # Resolution receives only opaque authorization and protocol signing facts;
    # application receives the selected context and bounded mutable request.
    assert tuple(inspect.signature(supports).parameters) == (
        "self",
        "authorization",
        "body_signing_requirement",
    )
    assert get_type_hints(supports) == {
        "authorization": Authorization,
        "body_signing_requirement": BodySigningRequirement,
        "return": frozenset[BodySigningMode],
    }
    assert tuple(inspect.signature(apply).parameters) == (
        "self",
        "authorization",
        "context",
        "request",
    )
    assert get_type_hints(apply) == {
        "authorization": Authorization,
        "context": AuthorizationContext,
        "request": MutableTransportRequest,
        "return": type(None),
    }
    assert not inspect.iscoroutinefunction(supports)
    assert inspect.iscoroutinefunction(apply)


def test_authorization_handler_requires_complete_behavior_surface() -> None:
    """Reject component metadata without matching and application operations."""
    incomplete = _IncompleteHandler()

    # Descriptor conformance alone cannot select or execute authorization.
    assert not isinstance(incomplete, AuthorizationHandler)


def test_authorization_handler_excludes_transport_and_lifecycle_ownership() -> None:
    """Keep network dispatch, request freezing, and registries out of handlers."""
    handler = _handler()

    # Authorization owns bounded replacements only; Runtime freezes and Transport
    # sends the final request after successful apply.
    for forbidden_member in (
        "send",
        "fetch",
        "freeze",
        "encode",
        "decode",
        "register",
    ):
        assert not hasattr(handler, forbidden_member)
