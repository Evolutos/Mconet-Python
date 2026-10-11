"""Tests for bearer authorization configuration."""

from collections.abc import Callable
from typing import cast

from mconet.auth.basic.bearer_authorization import (
    BEARER_AUTHORIZATION_KIND,
    BearerAuthorization,
)
from mconet.core.domain import Authorization, OpenIdentifier
from mconet.core.spi import AuthorizationContext, CredentialSource, CredentialValue


class _IdleCredentialSource:
    """Credential source that records whether resolution was attempted."""

    def __init__(self) -> None:
        """Start with no resolution attempts."""
        self.calls = 0

    async def resolve(self, context: AuthorizationContext) -> CredentialValue:
        """Fail if authorization configuration tries to read a token."""
        del context
        self.calls += 1
        raise AssertionError("authorization definition must not resolve credentials")

    def __repr__(self) -> str:
        """Expose a marker that authorization rendering must not copy."""
        return "bearer-token-marker"


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


def test_bearer_authorization_takes_the_token_only_from_its_source() -> None:
    """Verify the decision stores a source and no token text."""
    source = _IdleCredentialSource()
    authorization = BearerAuthorization(source)

    # The source identity is the token supplier. Nothing on the decision can
    # be mistaken for the token itself.
    assert isinstance(authorization, Authorization)
    assert isinstance(source, CredentialSource)
    assert authorization.credential_source is source
    assert authorization.kind is BEARER_AUTHORIZATION_KIND
    assert authorization.kind == OpenIdentifier("authorization.bearer")
    assert source.calls == 0
    assert not hasattr(authorization, "token")
    assert not hasattr(authorization, "prefix")
    assert not hasattr(authorization, "header_name")
    rendered = repr(authorization)
    assert "bearer-token-marker" not in rendered
    assert "credential_source=<CredentialSource>" in rendered


def test_bearer_authorization_rejects_a_direct_token_and_wrong_source() -> None:
    """Verify a token string cannot replace the credential source."""
    source = _IdleCredentialSource()
    construct = cast(Callable[..., BearerAuthorization], BearerAuthorization)

    _assert_raises(
        TypeError,
        lambda: construct("bearer-token-value"),
        "credential_source must implement CredentialSource",
    )
    _assert_raises(
        TypeError,
        lambda: construct(source, "bearer-token-value"),
        "kind must be an OpenIdentifier",
    )
    _assert_raises(
        ValueError,
        lambda: BearerAuthorization(source, OpenIdentifier("authorization.other")),
        "kind must be authorization.bearer",
    )
    assert source.calls == 0


def test_bearer_authorization_rejects_added_token_state() -> None:
    """Verify callers cannot attach a token after construction."""
    source = _IdleCredentialSource()
    authorization = BearerAuthorization(source)

    _assert_raises(
        AttributeError,
        lambda: setattr(authorization, "token", "bearer-token-value"),
        "does not accept attributes",
    )
    assert authorization.credential_source is source
    assert source.calls == 0
