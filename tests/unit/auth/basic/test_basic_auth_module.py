"""Tests for the auth-basic module boundary."""

import mconet.auth.basic
from mconet.auth.basic import NO_AUTHORIZATION_KIND, NoAuthorization


def test_basic_auth_exports_the_explicit_no_authorization_decision() -> None:
    """Verify the module publishes only the credential-free decision."""
    # API key and bearer types stay out of this export until their own
    # implementations define header and credential boundaries.
    assert mconet.auth.basic.__all__ == (
        "NO_AUTHORIZATION_KIND",
        "NoAuthorization",
    )
    assert mconet.auth.basic.NoAuthorization is NoAuthorization
    assert mconet.auth.basic.NO_AUTHORIZATION_KIND is NO_AUTHORIZATION_KIND
