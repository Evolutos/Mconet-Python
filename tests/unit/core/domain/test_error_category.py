"""Open-value tests for normalized error categories."""

import json
from collections.abc import Callable
from dataclasses import FrozenInstanceError
from typing import cast

from mconet.core.domain import ErrorCategory, OpenIdentifier

_STANDARD_CATEGORIES = (
    "invalid_request",
    "invalid_component_configuration",
    "unsupported_feature",
    "authentication",
    "permission",
    "rate_limit",
    "content_filter",
    "context_length",
    "timeout",
    "cancelled",
    "network",
    "serialization",
    "deserialization",
    "protocol",
    "model_service",
    "unknown",
)


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


def test_error_category_accepts_every_standard_category() -> None:
    """Verify the normalized category directory uses valid stable identifiers."""
    categories = tuple(
        ErrorCategory(OpenIdentifier(value)) for value in _STANDARD_CATEGORIES
    )

    assert tuple(str(category) for category in categories) == _STANDARD_CATEGORIES


def test_error_category_preserves_unknown_future_categories() -> None:
    """Verify a valid category introduced by an integration remains exact."""
    identifier = OpenIdentifier("vendor.future_quota")
    category = ErrorCategory(identifier)

    assert category.id is identifier
    assert str(category) == "vendor.future_quota"
    assert category not in {
        ErrorCategory(OpenIdentifier(value)) for value in _STANDARD_CATEGORIES
    }


def test_error_category_round_trips_unknown_value_through_json() -> None:
    """Verify wire serialization never replaces an unknown category."""
    category = ErrorCategory(OpenIdentifier("vendor.future_quota"))

    # Open values serialize as their exact identifier text. Reconstruction uses
    # the same public value path as known categories and performs no fallback.
    encoded = json.dumps({"category": str(category)})
    decoded = cast(dict[str, str], json.loads(encoded))
    restored = ErrorCategory(OpenIdentifier(decoded["category"]))

    assert restored == category
    assert str(restored) == "vendor.future_quota"


def test_error_category_has_immutable_value_semantics() -> None:
    """Verify equality, hashing, and immutability use the open identifier."""
    first = ErrorCategory(OpenIdentifier("timeout"))
    same = ErrorCategory(OpenIdentifier("timeout"))
    different = ErrorCategory(OpenIdentifier("network"))

    assert first == same
    assert hash(first) == hash(same)
    assert first != different
    assert first != OpenIdentifier("timeout")
    _assert_raises(
        FrozenInstanceError,
        lambda: first.__setattr__("id", OpenIdentifier("network")),
        "cannot assign to field",
    )


def test_error_category_rejects_invalid_identifiers() -> None:
    """Verify category IDs satisfy the portable open-identifier contract."""
    for value in ("", "Invalid_Request", "invalid request", "invalid/request"):
        _assert_raises(
            ValueError,
            lambda value=value: ErrorCategory(OpenIdentifier(value)),
            "OpenIdentifier",
        )


def test_error_category_requires_open_identifier() -> None:
    """Verify dynamic callers cannot replace the nominal identifier type."""
    _assert_raises(
        TypeError,
        lambda: ErrorCategory(cast(OpenIdentifier, "timeout")),
        "id must be an OpenIdentifier",
    )
