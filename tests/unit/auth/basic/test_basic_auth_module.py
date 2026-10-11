"""Tests for the auth-basic module boundary."""

import mconet.auth.basic
from mconet.auth.basic import (
    API_KEY_HEADER_AUTHORIZATION_KIND,
    BEARER_AUTHORIZATION_KIND,
    NO_AUTHORIZATION_KIND,
    ApiKeyHeaderAuthorization,
    BearerAuthorization,
    NoAuthorization,
)


def test_basic_auth_exports_defined_authorization_decisions() -> None:
    """Verify the module publishes the three built-in authorization decisions."""
    assert mconet.auth.basic.__all__ == (
        "API_KEY_HEADER_AUTHORIZATION_KIND",
        "BEARER_AUTHORIZATION_KIND",
        "NO_AUTHORIZATION_KIND",
        "ApiKeyHeaderAuthorization",
        "BearerAuthorization",
        "NoAuthorization",
    )
    assert mconet.auth.basic.NoAuthorization is NoAuthorization
    assert mconet.auth.basic.NO_AUTHORIZATION_KIND is NO_AUTHORIZATION_KIND
    assert mconet.auth.basic.ApiKeyHeaderAuthorization is ApiKeyHeaderAuthorization
    assert (
        mconet.auth.basic.API_KEY_HEADER_AUTHORIZATION_KIND
        is API_KEY_HEADER_AUTHORIZATION_KIND
    )
    assert mconet.auth.basic.BearerAuthorization is BearerAuthorization
    assert mconet.auth.basic.BEARER_AUTHORIZATION_KIND is BEARER_AUTHORIZATION_KIND
