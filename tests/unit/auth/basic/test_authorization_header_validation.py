"""Tests for authorization header name validation."""

from typing import cast

from mconet.auth.basic.authorization_header_validation import (
    validate_authorization_header_name,
)
from mconet.core.domain.model_interaction_error import ModelInteractionError

_INVALID_NAMES = ("", " ", ":", "X:Api-Key", "X Api-Key", "X-Api-Key\r", "名称")
_STABLE_MESSAGE = "Authorization header name is not an HTTP token."
_VALID_NAMES = ("X-Api-Key", "Authorization", "!")


def test_authorization_header_name_rejects_non_tokens_with_one_error() -> None:
    """Verify blank, colon, and other illegal names share one content-free error."""
    for name in _INVALID_NAMES:
        try:
            validate_authorization_header_name(name)
        except ModelInteractionError as error:
            assert error.code == "invalid_authorization_header_name"
            assert error.message == _STABLE_MESSAGE
            assert str(error.category.id) == "invalid_request"
            assert str(error.phase.id) == "authentication"
            # A blank or space can occur inside the stable message. Every other
            # rejected name must stay out of the error text.
            if name and name not in _STABLE_MESSAGE:
                assert name not in str(error)
        else:
            raise AssertionError("Expected an illegal header name to fail.")


def test_authorization_header_name_accepts_an_http_token() -> None:
    """Verify a token name is left unchanged and does not fail."""
    for name in _VALID_NAMES:
        validate_authorization_header_name(name)


def test_authorization_header_name_requires_text() -> None:
    """Verify a non-string name fails before any token rule runs."""
    try:
        validate_authorization_header_name(cast(str, None))
    except TypeError as error:
        assert "must be a string" in str(error)
    else:
        raise AssertionError("Expected a non-string header name to fail.")
