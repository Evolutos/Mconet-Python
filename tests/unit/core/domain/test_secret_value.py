"""Access-boundary tests for SecretValue."""

import json
import pickle
from collections.abc import Callable
from typing import cast

from mconet.core.domain import AuthorizedSecretConsumer, Bytes, SecretValue


class _AuthorizationHandler(AuthorizedSecretConsumer):
    """Represent a selected authorization handler in boundary tests."""


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


def test_secret_value_reveals_strings_and_bytes_to_authorized_consumers() -> None:
    """Verify the sole read method retains exact string and byte plaintext."""
    consumer = _AuthorizationHandler()
    text_secret = SecretValue("placeholder-token")
    byte_secret = SecretValue(Bytes(b"placeholder-bytes"))

    assert text_secret.reveal(consumer) == "placeholder-token"
    assert byte_secret.reveal(consumer) == Bytes(b"placeholder-bytes")


def test_secret_value_rejects_unauthorized_consumers() -> None:
    """Verify arbitrary objects cannot cross the explicit reveal boundary."""
    _assert_raises(
        TypeError,
        lambda: SecretValue("placeholder-token").reveal(
            cast(AuthorizedSecretConsumer, object())
        ),
        "consumer is not authorized",
    )


def test_authorized_secret_consumer_requires_concrete_handler() -> None:
    """Verify the marker cannot itself be used as an authorization capability."""
    _assert_raises(
        TypeError,
        AuthorizedSecretConsumer,
        "concrete authorization handler",
    )


def test_secret_value_has_no_public_plaintext_property_and_is_immutable() -> None:
    """Verify plaintext cannot be read or replaced through ordinary attributes."""
    secret = SecretValue("placeholder-token")

    assert not hasattr(secret, "value")
    _assert_raises(TypeError, lambda: vars(secret), "__dict__ attribute")
    _assert_raises(
        AttributeError,
        lambda: secret.__setattr__("value", "replacement"),
        "immutable",
    )


def test_secret_value_rejects_unsupported_plaintext_types() -> None:
    """Verify mutable bytes and arbitrary objects cannot become secret storage."""
    for value in (bytearray(b"bytes"), 1):
        _assert_raises(
            TypeError,
            lambda value=value: SecretValue(cast(str, value)),
            "string or Bytes",
        )


def test_secret_value_rejects_ordinary_serialization() -> None:
    """Verify JSON and pickle cannot encode the secret object or its state."""
    secret = SecretValue("placeholder-token")

    _assert_raises(
        TypeError,
        lambda: json.dumps(secret),
        "not JSON serializable",
    )
    _assert_raises(
        TypeError,
        lambda: pickle.dumps(secret),
        "cannot be serialized",
    )
