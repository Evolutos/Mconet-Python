"""Tests that system HTTP TLS verification cannot be turned off."""

from collections.abc import Callable
from typing import cast

from mconet.transport.http_system import HttpTlsPolicy, system_http_tls_policy


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return
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
