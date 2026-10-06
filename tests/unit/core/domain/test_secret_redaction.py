"""Redaction tests for SecretValue presentation boundaries."""

import inspect
import io
import json
import logging
import pprint
import traceback
from collections.abc import Callable

from mconet.core.domain import SecretValue

_PLACEHOLDER_VALUE = "placeholder-sensitive-value"
_REDACTED_TEXT = "[REDACTED]"


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


def test_secret_value_redacts_string_repr_and_formatting() -> None:
    """Verify direct and container presentation never include plaintext."""
    secret = SecretValue(_PLACEHOLDER_VALUE)
    rendered = (
        str(secret),
        repr(secret),
        f"{secret}",
        f"{secret!r}",
        f"{secret:>20}",
        repr({"secret": secret}),
        pprint.pformat([secret]),
    )

    assert all(_PLACEHOLDER_VALUE not in value for value in rendered)
    assert all(_REDACTED_TEXT in value for value in rendered)


def test_secret_value_redacts_lazy_logging_arguments() -> None:
    """Verify percent-style logging formats both string and repr safely."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    logger = logging.getLogger("mconet.tests.secret-redaction")
    previous_handlers = logger.handlers[:]
    previous_propagate = logger.propagate
    previous_level = logger.level
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.INFO)
    try:
        secret = SecretValue(_PLACEHOLDER_VALUE)
        logger.info("secret=%s secret_repr=%r", secret, secret)
        handler.flush()
    finally:
        logger.handlers = previous_handlers
        logger.propagate = previous_propagate
        logger.setLevel(previous_level)
        handler.close()

    output = stream.getvalue()
    assert _PLACEHOLDER_VALUE not in output
    assert output.count(_REDACTED_TEXT) == 2


def test_secret_value_json_fallback_is_redacted() -> None:
    """Verify explicit string fallback emits only the fixed marker."""
    secret = SecretValue(_PLACEHOLDER_VALUE)

    encoded = json.dumps({"secret": secret}, default=str)

    assert json.loads(encoded) == {"secret": _REDACTED_TEXT}
    assert _PLACEHOLDER_VALUE not in encoded


def test_secret_value_hides_plaintext_from_ordinary_inspection() -> None:
    """Verify dir, getattr, and inspect member enumeration omit the slot value."""
    secret = SecretValue(_PLACEHOLDER_VALUE)
    private_name = "_SecretValue__value"

    assert private_name not in dir(secret)
    _assert_raises(
        AttributeError,
        lambda: getattr(secret, private_name),
        "only accessible through reveal",
    )
    members = inspect.getmembers(secret)
    rendered_members = repr(members)
    assert private_name not in {name for name, _ in members}
    assert _PLACEHOLDER_VALUE not in rendered_members


def test_secret_value_redacts_exception_text_and_tracebacks() -> None:
    """Verify exception args, repr, and formatted tracebacks remain safe."""
    secret = SecretValue(_PLACEHOLDER_VALUE)
    try:
        raise ValueError("authorization failed", secret)
    except ValueError as error:
        rendered = (
            str(error),
            repr(error),
            "".join(traceback.format_exception(error)),
        )

    assert all(_PLACEHOLDER_VALUE not in value for value in rendered)
    assert all(_REDACTED_TEXT in value for value in rendered)
