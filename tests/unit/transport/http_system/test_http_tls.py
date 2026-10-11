"""Tests that system HTTP TLS verification cannot be turned off."""

import ssl
from collections.abc import Callable
from typing import cast

from mconet.core.domain import ModelInteractionError, OpenIdentifier
from mconet.transport.http_system import (
    HttpTlsPolicy,
    ensure_secure_http_tls,
    system_http_tls_policy,
)


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> BaseException:
    """Return the expected exception after checking its stable message fragment."""
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return error
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_system_http_tls_policy_always_verifies_the_peer() -> None:
    """Verify the shared policy enables both certificate and hostname checks."""
    policy = system_http_tls_policy()

    assert policy is system_http_tls_policy()
    assert policy == HttpTlsPolicy()
    assert policy.verifies_certificates is True
    assert policy.verifies_hostname is True
    assert "False" not in repr(policy)


def test_system_http_tls_policy_rejects_a_disabled_check() -> None:
    """Verify verification flags are not constructor arguments."""
    construct = cast(Callable[..., HttpTlsPolicy], HttpTlsPolicy)
    _assert_raises(
        TypeError,
        lambda: construct(verifies_certificates=False),
        "verifies_certificates",
    )
    _assert_raises(
        TypeError,
        lambda: construct(verifies_hostname=False),
        "verifies_hostname",
    )


def test_system_http_tls_policy_rejects_assignment() -> None:
    """Verify an existing policy cannot store a disabled check."""
    policy = system_http_tls_policy()

    def disable_certificates() -> None:
        object.__setattr__(policy, "verifies_certificates", False)

    _assert_raises(AttributeError, disable_certificates, "verifies_certificates")
    assert policy.verifies_certificates is True
    assert policy.verifies_hostname is True


def test_ensure_secure_http_tls_accepts_only_confirming_options() -> None:
    """Verify an empty or confirming configuration keeps the system policy."""
    assert ensure_secure_http_tls(None) is system_http_tls_policy()
    assert ensure_secure_http_tls({}) is system_http_tls_policy()
    assert (
        ensure_secure_http_tls(
            {"verify": True, "check_hostname": True, "cert_reqs": ssl.CERT_REQUIRED}
        )
        is system_http_tls_policy()
    )


def test_ensure_secure_http_tls_rejects_disabled_verification() -> None:
    """Verify disabled checks fail before a connection and omit option values."""
    secret = "/tmp/tls-secret-certificate"
    for options in (
        {"verify": False},
        {"check_hostname": False},
        {"cert_reqs": ssl.CERT_NONE},
        {"verify_mode": "CERT_NONE"},
        {"ca_certs": secret},
    ):
        error = cast(
            ModelInteractionError,
            _assert_raises(
                ModelInteractionError,
                lambda options=options: ensure_secure_http_tls(options),
                "cannot be disabled",
            ),
        )
        assert error.code == "insecure_http_tls"
        assert error.category.id == OpenIdentifier("invalid_component_configuration")
        assert error.phase.id == OpenIdentifier("transport")
        assert secret not in str(error)
        assert error.cause is None
