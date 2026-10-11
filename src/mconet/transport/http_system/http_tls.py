"""TLS verification rules for the system HTTP transport."""

from __future__ import annotations

import ssl
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import cast

from mconet.core.domain.error_category import ErrorCategory
from mconet.core.domain.interaction_phase import InteractionPhase
from mconet.core.domain.model_interaction_error import ModelInteractionError
from mconet.core.domain.open_identifier import OpenIdentifier

_CONFIGURATION_CATEGORY = ErrorCategory(
    OpenIdentifier("invalid_component_configuration")
)
_TRANSPORT_PHASE = InteractionPhase(OpenIdentifier("transport"))
_INSECURE_TLS_CODE = "insecure_http_tls"
_INSECURE_TLS_MESSAGE = "HTTP TLS verification cannot be disabled."
_CONFIRMING_FLAGS = frozenset({"verify", "check_hostname"})
_CERTIFICATE_MODES = frozenset({"cert_reqs", "verify_mode"})


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


def ensure_secure_http_tls(
    options: Mapping[str, object] | None = None,
) -> HttpTlsPolicy:
    """Reject TLS options that would disable certificate or hostname checks.

    ``None`` and an empty mapping mean the system policy. A recognized flag
    may only confirm that verification stays enabled. Any other TLS option is
    rejected before a connection is opened, because it could replace the
    platform trust decision. Option values are omitted from the error.

    Args:
        options: Optional TLS overrides. This is not an ``SSLContext``.

    Returns:
        The system TLS policy when every supplied option confirms verification.

    Raises:
        TypeError: If ``options`` is not a string-key mapping or ``None``.
        ModelInteractionError: If an option would weaken TLS. The stable code
            is ``insecure_http_tls``.
    """
    if options is None:
        return _SYSTEM_HTTP_TLS_POLICY
    candidate = cast(object, options)
    if not isinstance(candidate, Mapping):
        raise TypeError("options must be a mapping or None.")
    for key, value in _tls_items(cast(object, candidate)):
        # An unrecognized option can carry a context or trust store that skips
        # verification. Only explicit confirmations of the system policy pass.
        if not _confirms_verification(key, value):
            raise _insecure_tls_error()
    return _SYSTEM_HTTP_TLS_POLICY


def _tls_items(options: object) -> tuple[tuple[str, object], ...]:
    """Return TLS options after checking that each key is a string.

    Args:
        options: Candidate TLS mapping already known to be a mapping.

    Returns:
        Key and value pairs in mapping order.

    Raises:
        TypeError: If a key is not a string.
    """
    mapping = cast(Mapping[object, object], options)
    items: list[tuple[str, object]] = []
    for item in cast(Iterable[object], mapping.items()):
        if not isinstance(item, tuple):
            raise TypeError("options keys must be strings.")
        pair = cast(tuple[object, ...], item)
        if len(pair) != 2 or not isinstance(pair[0], str):
            raise TypeError("options keys must be strings.")
        items.append((pair[0], pair[1]))
    return tuple(items)


def _confirms_verification(name: str, value: object) -> bool:
    """Return whether one option repeats the system verification rule.

    Args:
        name: TLS option name.
        value: Supplied option value.

    Returns:
        Whether the option leaves certificate and hostname checks enabled.
    """
    if name in _CONFIRMING_FLAGS:
        return value is True
    if name in _CERTIFICATE_MODES:
        return value == ssl.CERT_REQUIRED or value == "CERT_REQUIRED"
    return False


def _insecure_tls_error() -> ModelInteractionError:
    """Create the failure for a TLS option that weakens verification.

    Returns:
        A configuration error that does not include the rejected option value.
    """
    # The value is omitted because it can name a private certificate path.
    return ModelInteractionError(
        category=_CONFIGURATION_CATEGORY,
        phase=_TRANSPORT_PHASE,
        code=_INSECURE_TLS_CODE,
        message=_INSECURE_TLS_MESSAGE,
    )
