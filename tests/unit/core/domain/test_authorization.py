"""Structural and serialization-boundary tests for Authorization."""

import json
from dataclasses import dataclass

from mconet.core.domain import Authorization, OpenIdentifier, SecretValue


@dataclass(frozen=True, slots=True)
class _CustomAuthorization:
    """Custom authorization proving the protocol has no closed type registry."""

    kind: OpenIdentifier
    credential: SecretValue
    signing_region: str


def test_authorization_accepts_opaque_custom_implementation() -> None:
    """Verify custom credentials remain owned by their concrete authorization."""
    authorization = _CustomAuthorization(
        kind=OpenIdentifier("authorization.vendor_signature"),
        credential=SecretValue("placeholder-credential"),
        signing_region="region-a",
    )

    # Structural recognition depends only on the open kind property. The core
    # protocol neither requires inheritance nor inspects provider-owned fields.
    assert isinstance(authorization, Authorization)
    assert authorization.kind == OpenIdentifier("authorization.vendor_signature")
    assert authorization.signing_region == "region-a"
    assert str(authorization.credential) == "[REDACTED]"


def test_authorization_requires_kind_property() -> None:
    """Verify arbitrary credential containers cannot satisfy the protocol."""

    @dataclass(frozen=True, slots=True)
    class _MissingKind:
        """Represent credentials that omit handler-selection identity."""

        credential: SecretValue

    # A credential alone is insufficient: every implementation must expose the
    # open identifier that a later resolver can use without reading plaintext.
    candidate = _MissingKind(SecretValue("placeholder-credential"))
    assert not isinstance(candidate, Authorization)


def test_authorization_is_not_an_ordinary_payload_value() -> None:
    """Verify the runtime component cannot enter generic JSON payload encoding."""
    authorization = _CustomAuthorization(
        kind=OpenIdentifier("authorization.vendor_signature"),
        credential=SecretValue("placeholder-credential"),
        signing_region="region-a",
    )

    # Authorization carries a SecretValue and is intentionally absent from the
    # JSON domain. Generic payload serialization must reject the whole object.
    try:
        json.dumps(authorization)
    except TypeError as error:
        assert "not JSON serializable" in str(error)
    else:
        raise AssertionError("Authorization must not be JSON serializable.")
