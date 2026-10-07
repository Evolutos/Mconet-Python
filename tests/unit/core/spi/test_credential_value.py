"""Structural and security tests for the credential value contract."""

from __future__ import annotations

import inspect
import io
import json
import logging
import pickle
from collections.abc import Callable
from typing import Never, SupportsIndex, cast, get_type_hints

from mconet.core.domain import (
    AuthorizedSecretConsumer,
    OpenIdentifier,
    SecretValue,
)
from mconet.core.spi import CredentialValue

_PLACEHOLDER_VALUE = "placeholder-credential-value"
_REDACTED_TEXT = "[REDACTED]"


class _AuthorizationHandler(AuthorizedSecretConsumer):
    """Represent a selected handler permitted to consume credential plaintext."""


class _Credential:
    """Ordinary secure credential implementation used by contract tests."""

    __slots__ = ("_kind", "_secret")

    def __init__(self, kind: OpenIdentifier, secret: SecretValue) -> None:
        """Store a non-sensitive discriminator and protected secret container."""
        # The wrapper never copies plaintext out of SecretValue during storage;
        # only the explicit reveal path can cross the consumer boundary.
        self._kind = kind
        self._secret = secret

    @property
    def kind(self) -> OpenIdentifier:
        """Return the exact non-sensitive credential discriminator."""
        # Kind selection is safe because it contains no token, key, or derived
        # credential material and does not access SecretValue plaintext.
        return self._kind

    def reveal(self, consumer: AuthorizedSecretConsumer) -> object:
        """Delegate protected access to the existing nominal secret boundary."""
        # SecretValue performs the nominal handler check before returning the
        # exact immutable secret; the wrapper cannot weaken that authorization.
        return self._secret.reveal(consumer)

    def __str__(self) -> str:
        """Return a fixed redaction marker instead of credential material."""
        # Fixed output prevents kind-specific formatting from leaking length,
        # prefix, account, provider, or other properties of protected data.
        return _REDACTED_TEXT

    def __repr__(self) -> str:
        """Return the same fixed marker used by logs and containers."""
        # Container repr and lazy logging therefore remain safe automatically.
        return _REDACTED_TEXT

    def __format__(self, format_spec: str) -> str:
        """Apply formatting only to the redaction marker."""
        # Alignment and width affect safe marker text rather than plaintext.
        return format(_REDACTED_TEXT, format_spec)

    def __getstate__(self) -> Never:
        """Reject state-based serializers before they inspect protected slots."""
        # No ordinary persistence representation is valid for a live credential.
        raise TypeError("CredentialValue cannot be serialized.")

    def __reduce_ex__(self, protocol: SupportsIndex) -> Never:
        """Reject pickle and copy protocols requesting reconstruction state."""
        # Discard the protocol number without allowing it to select a weaker path.
        del protocol
        raise TypeError("CredentialValue cannot be serialized.")


class _IncompleteCredential:
    """Credential-shaped fixture intentionally missing controlled reveal."""

    @property
    def kind(self) -> OpenIdentifier:
        """Return a valid discriminator while omitting the required read path."""
        # A kind alone cannot grant access to or satisfy the credential contract.
        return OpenIdentifier("credential.incomplete")


def _credential() -> _Credential:
    """Build one secure ordinary credential implementation."""
    # The placeholder is recognized test-only data, while SecretValue still
    # exercises the same controlled storage used by production authorization.
    return _Credential(
        OpenIdentifier("credential.bearer"),
        SecretValue(_PLACEHOLDER_VALUE),
    )


def _accept_credential(credential: CredentialValue) -> CredentialValue:
    """Return a credential after crossing the statically checked protocol boundary."""
    # Pyright verifies an ordinary implementation without SDK inheritance,
    # registration, a fixed provider enum, or a concrete plaintext result type.
    return credential


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require one action to raise the expected exception and message fragment."""
    try:
        action()
    except exception_type as error:
        # Matching stable security wording avoids accepting an unrelated failure
        # that happens before the protected boundary is exercised.
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_credential_value_accepts_secure_ordinary_structural_class() -> None:
    """Require only the open kind and controlled reveal behavior surface."""
    credential = _credential()

    accepted = _accept_credential(credential)

    # Static and runtime conformance agree without inheritance, a registry ID,
    # a closed credential-kind enum, or a public plaintext attribute.
    assert accepted is credential
    assert isinstance(credential, CredentialValue)
    assert credential.kind == OpenIdentifier("credential.bearer")
    assert not hasattr(credential, "value")


def test_credential_value_reveals_only_to_authorized_consumer() -> None:
    """Preserve plaintext identity behind the nominal authorization boundary."""
    credential = _credential()
    handler = _AuthorizationHandler()

    revealed = credential.reveal(handler)

    # Authorized access returns exact protected data, while arbitrary objects
    # cannot satisfy the nominal marker through structural coincidence.
    assert revealed == _PLACEHOLDER_VALUE
    _assert_raises(
        TypeError,
        lambda: credential.reveal(cast(AuthorizedSecretConsumer, object())),
        "consumer is not authorized",
    )


def test_credential_value_redacts_all_ordinary_text_presentation() -> None:
    """Keep plaintext out of direct, container, formatted, and logging output."""
    credential = _credential()
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    logger = logging.getLogger("mconet.tests.credential-redaction")
    previous_handlers = logger.handlers[:]
    previous_propagate = logger.propagate
    previous_level = logger.level
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.INFO)
    try:
        # Lazy percent-style logging exercises both string and repr conversions
        # used by common structured and unstructured logging integrations.
        logger.info("credential=%s credential_repr=%r", credential, credential)
        handler.flush()
    finally:
        # Restore shared logger state so this security test cannot affect later
        # tests even when formatting or emission raises unexpectedly.
        logger.handlers = previous_handlers
        logger.propagate = previous_propagate
        logger.setLevel(previous_level)
        handler.close()

    rendered = (
        str(credential),
        repr(credential),
        f"{credential}",
        f"{credential!r}",
        f"{credential:>20}",
        repr({"credential": credential}),
        stream.getvalue(),
    )
    # Every ordinary representation contains a fixed marker and never plaintext.
    assert all(_PLACEHOLDER_VALUE not in value for value in rendered)
    assert all(_REDACTED_TEXT in value for value in rendered)


def test_credential_value_rejects_ordinary_serialization() -> None:
    """Prevent JSON and pickle from producing a credential representation."""
    credential = _credential()

    # JSON has no default representation, while pickle reaches the explicit
    # rejection hook before it can enumerate protected slots or secret state.
    _assert_raises(
        TypeError,
        lambda: json.dumps(credential),
        "not JSON serializable",
    )
    _assert_raises(
        TypeError,
        lambda: pickle.dumps(credential),
        "cannot be serialized",
    )


def test_credential_value_has_exact_method_surface() -> None:
    """Lock the discriminator and controlled reveal signatures."""
    kind_property = cast(property, CredentialValue.__dict__["kind"])
    kind_getter = kind_property.fget
    assert kind_getter is not None
    kind_annotations = get_type_hints(kind_getter)
    reveal_method = CredentialValue.reveal
    reveal_annotations = get_type_hints(reveal_method)

    # The opaque object return supports future compound credentials without Any,
    # while only the nominal consumer can request protected runtime data.
    assert kind_annotations == {"return": OpenIdentifier}
    assert tuple(inspect.signature(reveal_method).parameters) == (
        "self",
        "consumer",
    )
    assert reveal_annotations == {
        "consumer": AuthorizedSecretConsumer,
        "return": object,
    }
    assert not inspect.iscoroutinefunction(reveal_method)


def test_credential_value_requires_complete_behavior_surface() -> None:
    """Reject a discriminator-only object without controlled reveal behavior."""
    incomplete = _IncompleteCredential()

    # Open kind metadata cannot substitute for the mandatory secret access path.
    assert not isinstance(incomplete, CredentialValue)
