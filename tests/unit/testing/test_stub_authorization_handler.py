"""Request boundary and failure tests for StubAuthorizationHandler."""

from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass, field
from typing import cast, get_type_hints

from mconet.core.domain import (
    Authorization,
    Bytes,
    Extensions,
    HeaderField,
    Headers,
    MediaType,
    ModelDescriptor,
    ModelTarget,
    NamedModel,
    OpenIdentifier,
    QueryParameter,
    QueryParameters,
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
    TransportRequest,
)
from mconet.testing import StubAuthorizationHandler


def _empty_extensions() -> Extensions:
    """Create independent portable target extension storage."""
    # Fresh mappings prevent fixture construction from sharing mutable input
    # before AuthorizationContext creates its read-only snapshot.
    return {}


@dataclass(frozen=True, slots=True)
class _Authorization:
    """Opaque non-secret authorization fixture for Stub calls."""

    kind: OpenIdentifier
    """Open handler-selection discriminator."""


@dataclass(frozen=True, slots=True)
class _Target:
    """Complete structural model target retained by authorization context."""

    service_id: OpenIdentifier
    """Open service identity."""

    protocol_id: OpenIdentifier
    """Open protocol identity."""

    model: ModelDescriptor
    """Exact model descriptor selected for the interaction."""

    deployment_id: str | None = None
    """Optional provider deployment identity."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Portable target extension facts."""


def _authorization() -> _Authorization:
    """Build one opaque authorization value without credential data."""
    # The Stub accepts the structural kind but deliberately performs no reveal,
    # provider-specific parsing, or request mutation.
    return _Authorization(OpenIdentifier("authorization.fixture"))


def _context() -> AuthorizationContext:
    """Build complete immutable facts for one authorization attempt."""
    # Runtime-selected time, target, transport, and mode remain explicit so the
    # Stub cannot infer them from the mutable request or a global clock.
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
    # Distinct immutable fields make snapshot detachment and no-op behavior
    # observable without placing credentials in the request.
    return MutableTransportRequest(
        method="POST",
        url=UriValue("https://models.example.test/v1/run", True),
        headers=Headers((HeaderField("X-Trace", "trace-value"),)),
        query=QueryParameters((QueryParameter("region", "east"),)),
        body=TransportBody(
            Bytes(b'{"input":"hello"}'),
            MediaType("application", "json"),
        ),
    )


def _stub(
    *,
    supported_modes: frozenset[BodySigningMode] = frozenset(("none",)),
    apply_error: BaseException | None = None,
) -> StubAuthorizationHandler:
    """Create one valid handler Stub with deterministic configuration."""
    # Constructor configuration remains explicit at the helper boundary while
    # common tests reuse the canonical no-signing mode.
    return StubAuthorizationHandler(
        ComponentDescriptor("Stub handler", "1", "application"),
        supported_modes,
        apply_error=apply_error,
    )


def _apply(stub: StubAuthorizationHandler, request: MutableTransportRequest) -> None:
    """Run one asynchronous authorization attempt to completion."""
    # asyncio.run gives synchronous tests an isolated event loop without adding
    # timing, background tasks, or external I/O to the Stub contract.
    asyncio.run(stub.apply(_authorization(), _context(), request))


def _assert_raises_identity(
    stub: StubAuthorizationHandler,
    request: MutableTransportRequest,
    expected: BaseException,
) -> None:
    """Require one apply call to raise the exact configured failure."""
    try:
        _apply(stub, request)
    except BaseException as error:
        # Identity proves the Stub neither wraps the authorization failure nor
        # replaces it with a credential, request, or transport error.
        assert error is expected
        return
    raise AssertionError(f"Expected {type(expected).__name__} to be raised.")


def test_stub_structurally_implements_authorization_handler() -> None:
    """Expose matching and asynchronous apply without inheritance."""
    stub = _stub()

    accepted: AuthorizationHandler = stub

    # Static and runtime recognition agree on the same ordinary object without a
    # component ID, provider base class, Registry, or secret-consumer capability.
    assert accepted is stub
    assert isinstance(stub, AuthorizationHandler)
    assert stub.descriptor.name == "Stub handler"


def test_stub_returns_exact_configured_supported_modes() -> None:
    """Report immutable compatibility facts without recording or side effects."""
    modes: frozenset[BodySigningMode] = frozenset(
        ("precomputed_digest", "buffered_digest")
    )
    stub = _stub(supported_modes=modes)

    result = stub.supports(
        _authorization(),
        BodySigningRequirement(
            required=True,
            acceptable_modes=("precomputed_digest", "buffered_digest"),
            max_buffer_bytes=1024,
        ),
    )

    # Identity proves the Stub does not intersect, reorder, or copy configured
    # modes; supports also leaves request histories untouched.
    assert result is modes
    assert stub.requests_before == ()
    assert stub.requests_after == ()


def test_stub_records_detached_before_and_after_request_snapshots() -> None:
    """Capture one successful no-op authorization boundary without freezing."""
    stub = _stub()
    request = _request()
    original_headers = request.headers

    _apply(stub, request)

    # Both immutable snapshots retain the complete unchanged request state, the
    # original builder remains open, and no authorization field is fabricated.
    assert len(stub.requests_before) == 1
    assert len(stub.requests_after) == 1
    before = stub.requests_before[0]
    after = stub.requests_after[0]
    assert isinstance(before, TransportRequest)
    assert isinstance(after, TransportRequest)
    assert before is not after
    assert before == after
    assert before.headers is original_headers
    assert after.headers is original_headers
    assert request.is_frozen is False
    assert request.headers.get_all("Authorization") == ()

    request.replace_headers(Headers((HeaderField("X-Later", "changed"),)))

    # Later mutation replaces only the builder's current immutable value; prior
    # test records remain time-bounded and cannot follow the mutable request.
    assert before.headers is original_headers
    assert after.headers is original_headers
    assert request.headers is not original_headers


def test_stub_records_unchanged_boundaries_before_raising_exact_error() -> None:
    """Expose a failed attempt without partial mutation or request freezing."""
    failure = RuntimeError("credential provider failed")
    stub = _stub(apply_error=failure)
    request = _request()

    _assert_raises_identity(stub, request, failure)

    # The aligned histories prove the failed no-op attempt observed both
    # boundaries while leaving every transport field and lifecycle state intact.
    assert len(stub.requests_before) == 1
    assert len(stub.requests_after) == 1
    assert stub.requests_before[0] == stub.requests_after[0]
    assert request.is_frozen is False
    assert request.headers.get_all("Authorization") == ()


def test_request_histories_preserve_order_and_immutable_membership() -> None:
    """Keep repeated invocation records ordered and externally immutable."""
    stub = _stub()
    first = _request()
    second = _request()
    second.replace_query(QueryParameters((QueryParameter("region", "west"),)))

    _apply(stub, first)
    first_before = stub.requests_before
    first_after = stub.requests_after
    _apply(stub, second)

    # Fresh tuple views cannot mutate internal membership, earlier views remain
    # time-bounded, and later histories preserve distinct invocation order.
    assert len(first_before) == 1
    assert len(first_after) == 1
    assert len(stub.requests_before) == 2
    assert len(stub.requests_after) == 2
    assert stub.requests_before[0].query.values[0].value == "east"
    assert stub.requests_before[1].query.values[0].value == "west"
    assert not hasattr(stub.requests_before, "append")


def test_stub_validates_configuration_and_dynamic_request_boundary() -> None:
    """Reject malformed setup and invalid request lifecycle inputs."""
    descriptor = ComponentDescriptor("Stub handler", "1", "application")
    invalid_calls = (
        (
            lambda: StubAuthorizationHandler(
                cast(ComponentDescriptor, object()), frozenset(("none",))
            ),
            TypeError,
            "descriptor must be a ComponentDescriptor",
        ),
        (
            lambda: StubAuthorizationHandler(
                descriptor,
                cast(frozenset[BodySigningMode], set(("none",))),
            ),
            TypeError,
            "supported_modes must be a frozenset",
        ),
        (
            lambda: StubAuthorizationHandler(
                descriptor,
                cast(frozenset[BodySigningMode], frozenset((1,))),
            ),
            TypeError,
            "supported_modes must contain strings",
        ),
        (
            lambda: StubAuthorizationHandler(
                descriptor,
                cast(frozenset[BodySigningMode], frozenset(("future_mode",))),
            ),
            ValueError,
            "supported_modes contains an unsupported mode",
        ),
        (
            lambda: StubAuthorizationHandler(
                descriptor,
                frozenset(("none",)),
                apply_error=cast(BaseException, "failure"),
            ),
            TypeError,
            "apply_error must be a BaseException or None",
        ),
        (
            lambda: asyncio.run(
                _stub().apply(
                    _authorization(),
                    _context(),
                    cast(MutableTransportRequest, object()),
                )
            ),
            TypeError,
            "request must be a MutableTransportRequest",
        ),
    )

    for action, exception_type, message in invalid_calls:
        try:
            action()
        except exception_type as error:
            # Stable diagnostics distinguish malformed Stub usage from an apply
            # failure that a configured authorization scenario intends to test.
            assert message in str(error)
        else:
            raise AssertionError("Expected invalid Stub usage to fail.")

    frozen_request = _request()
    frozen_request.freeze()
    try:
        _apply(_stub(), frozen_request)
    except RuntimeError as error:
        # Rejecting a closed window preserves Runtime ownership and avoids adding
        # misleading before/after records for an invalid authorization call.
        assert "request must remain open during authorization" in str(error)
    else:
        raise AssertionError("Expected frozen request authorization to fail.")


def test_stub_matches_handler_surface_without_adjacent_responsibilities() -> None:
    """Expose exact handler behavior plus required local request records."""
    stub = _stub()
    supports = StubAuthorizationHandler.supports
    apply = StubAuthorizationHandler.apply

    # Matching remains synchronous, application remains asynchronous, and both
    # concrete signatures resolve to the exact SPI annotations.
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

    # Snapshot records are the only local testing surface. Credential access,
    # mutation, freezing, transport, registry, and reconfiguration stay absent.
    for forbidden_member in (
        "calls",
        "configure",
        "reset",
        "reveal",
        "resolve_credential",
        "replace_headers",
        "freeze",
        "send",
        "register",
    ):
        assert not hasattr(stub, forbidden_member)
