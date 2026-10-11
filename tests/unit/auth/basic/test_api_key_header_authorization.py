"""Tests for header API key authorization configuration."""

from collections.abc import Callable
from typing import cast

from mconet.auth.basic import (
    API_KEY_HEADER_AUTHORIZATION_KIND,
    ApiKeyHeaderAuthorization,
)
from mconet.core.domain import Authorization, OpenIdentifier
from mconet.core.spi import AuthorizationContext, CredentialSource, CredentialValue


class _IdleCredentialSource:
    """Credential source that records whether resolution was attempted."""

    def __init__(self) -> None:
        """Start with no resolution attempts."""
        self.calls = 0

    async def resolve(self, context: AuthorizationContext) -> CredentialValue:
        """Fail if authorization configuration tries to read a credential."""
        del context
        self.calls += 1
        raise AssertionError("authorization definition must not resolve credentials")

    def __repr__(self) -> str:
        """Expose a marker that authorization rendering must not copy."""
        return "credential-source-marker"


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


def test_api_key_header_authorization_keeps_name_prefix_and_source_separate() -> None:
    """Verify the key is not stored or composed into the header configuration."""
    source = _IdleCredentialSource()
    authorization = ApiKeyHeaderAuthorization("X-Api-Key", "Key ", source)

    # The three inputs remain independent. The kind selects a handler later
    # and is not derived from the header name or prefix.
    assert isinstance(authorization, Authorization)
    assert isinstance(source, CredentialSource)
    assert authorization.header_name == "X-Api-Key"
    assert authorization.prefix == "Key "
    assert authorization.credential_source is source
    assert authorization.kind is API_KEY_HEADER_AUTHORIZATION_KIND
    assert source.calls == 0
    assert not hasattr(authorization, "credential")
    assert not hasattr(authorization, "api_key")
    assert "credential-source-marker" not in repr(authorization)
    assert "X-Api-Key" in repr(authorization)


def test_api_key_header_authorization_preserves_an_empty_prefix() -> None:
    """Verify an empty prefix stays explicit rather than becoming a default."""
    source = _IdleCredentialSource()
    authorization = ApiKeyHeaderAuthorization("Authorization", "", source)

    # An empty prefix means the source value is the entire header value. It is
    # not rewritten to a bearer scheme or dropped as missing configuration.
    assert authorization.prefix == ""
    assert authorization.header_name == "Authorization"
    assert authorization.credential_source is source


def test_api_key_header_authorization_rejects_invalid_field_types() -> None:
    """Verify name, prefix, source, and kind keep their declared types."""
    source = _IdleCredentialSource()
    cases = (
        (
            lambda: ApiKeyHeaderAuthorization(cast(str, None), "", source),
            TypeError,
            "header_name must be a string",
        ),
        (
            lambda: ApiKeyHeaderAuthorization("X-Api-Key", cast(str, 1), source),
            TypeError,
            "prefix must be a string",
        ),
        (
            lambda: ApiKeyHeaderAuthorization(
                "X-Api-Key", "", cast(CredentialSource, object())
            ),
            TypeError,
            "credential_source must implement CredentialSource",
        ),
        (
            lambda: ApiKeyHeaderAuthorization(
                "X-Api-Key",
                "",
                source,
                OpenIdentifier("authorization.other"),
            ),
            ValueError,
            "kind must be authorization.api_key_header",
        ),
    )

    for action, error_type, message in cases:
        _assert_raises(error_type, action, message)
        # A rejected constructor must not ask the valid source for a key.
        assert source.calls == 0


def test_api_key_header_authorization_is_immutable() -> None:
    """Verify callers cannot replace the source or attach key material."""
    authorization = ApiKeyHeaderAuthorization(
        "X-Api-Key",
        "Key ",
        _IdleCredentialSource(),
    )

    _assert_raises(
        AttributeError,
        lambda: setattr(authorization, "header_name", "Authorization"),
        "does not accept attributes",
    )
    _assert_raises(
        AttributeError,
        lambda: setattr(authorization, "credential", "not-a-key"),
        "does not accept attributes",
    )
    assert authorization.header_name == "X-Api-Key"
