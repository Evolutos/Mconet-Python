"""TLS verification rules for the system HTTP transport."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HttpTlsPolicy:
    """Platform TLS rules that always verify the peer.

    Certificate-chain verification and hostname verification are enabled.
    Trust anchors are the platform default. This value has no field, argument,
    or method that turns either check off, and it does not load a private key
    or open a connection.
    """

    @property
    def verifies_certificates(self) -> bool:
        """Return whether the peer certificate chain is verified."""
        # The result is fixed. A caller cannot store a different choice on
        # this value.
        return True

    @property
    def verifies_hostname(self) -> bool:
        """Return whether the certificate hostname is verified."""
        # Hostname verification stays paired with chain verification. Neither
        # check can be selected alone.
        return True


_SYSTEM_HTTP_TLS_POLICY = HttpTlsPolicy()


def system_http_tls_policy() -> HttpTlsPolicy:
    """Return the only TLS policy the system transport can use.

    Returns:
        The frozen policy. Certificate and hostname verification are enabled.
    """
    return _SYSTEM_HTTP_TLS_POLICY
