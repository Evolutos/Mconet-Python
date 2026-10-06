"""Positive Int64 validation tests for interaction resource limits."""

from collections.abc import Callable
from typing import cast

from mconet.core.domain import (
    InteractionResourceLimits,
    ResolvedInteractionResourceLimits,
    validate_resource_limits,
)

_MAX_SIGNED_INT64 = (1 << 63) - 1


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    # Match the field-level diagnostic so a failure in another limit cannot make
    # a negative validation test pass accidentally.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_resource_limits_validator_preserves_valid_unresolved_input() -> None:
    """Verify omitted and positive optional fields retain identity and values."""
    limits = InteractionResourceLimits(
        max_response_body_bytes=1,
        max_frame_bytes=_MAX_SIGNED_INT64,
    )

    # Validation never fills the omitted streaming-error field or copies the
    # immutable input; default resolution belongs to the following component.
    assert validate_resource_limits(limits) is limits
    assert limits.max_streaming_error_body_bytes is None


def test_resource_limits_validator_preserves_valid_resolved_input() -> None:
    """Verify complete positive limits at both valid boundaries retain identity."""
    limits = ResolvedInteractionResourceLimits(1, 2, _MAX_SIGNED_INT64)

    # The same complete object can flow directly to later configuration checks
    # after validation without normalization or reallocation.
    assert validate_resource_limits(limits) is limits


def test_resource_limits_validator_accepts_fully_omitted_unresolved_input() -> None:
    """Verify an empty unresolved layer remains valid before default merging."""
    limits = InteractionResourceLimits()

    # Absence means this layer has no override; it is not interpreted as zero or
    # an unlimited value by semantic validation.
    assert validate_resource_limits(limits) is limits


def test_resource_limits_validator_rejects_nonpositive_optional_fields() -> None:
    """Verify zero and negative values fail for every unresolved field."""
    invalid_limits = (
        (
            InteractionResourceLimits(max_response_body_bytes=0),
            "max_response_body_bytes",
        ),
        (
            InteractionResourceLimits(max_streaming_error_body_bytes=-1),
            "max_streaming_error_body_bytes",
        ),
        (
            InteractionResourceLimits(max_frame_bytes=0),
            "max_frame_bytes",
        ),
    )

    # Each independent optional override must satisfy the same positive rule;
    # absent neighboring fields do not hide the invalid supplied value.
    for limits, field_name in invalid_limits:
        _assert_raises(
            ValueError,
            lambda limits=limits: validate_resource_limits(limits),
            f"{field_name} must be positive",
        )


def test_resource_limits_validator_rejects_nonpositive_resolved_fields() -> None:
    """Verify every complete field is checked rather than only optional input."""
    invalid_limits = (
        (ResolvedInteractionResourceLimits(0, 2, 3), "max_response_body_bytes"),
        (
            ResolvedInteractionResourceLimits(1, -1, 3),
            "max_streaming_error_body_bytes",
        ),
        (ResolvedInteractionResourceLimits(1, 2, 0), "max_frame_bytes"),
    )

    # Resolved storage completeness does not imply semantic validity, so the
    # validator applies the positive rule to all three concrete values.
    for limits, field_name in invalid_limits:
        _assert_raises(
            ValueError,
            lambda limits=limits: validate_resource_limits(limits),
            f"{field_name} must be positive",
        )


def test_resource_limits_validator_rejects_positive_overflow_per_field() -> None:
    """Verify values above signed Int64 maximum fail for every limit field."""
    overflow = 1 << 63
    invalid_limits = (
        (
            InteractionResourceLimits(max_response_body_bytes=overflow),
            "max_response_body_bytes",
        ),
        (
            InteractionResourceLimits(max_streaming_error_body_bytes=overflow),
            "max_streaming_error_body_bytes",
        ),
        (
            ResolvedInteractionResourceLimits(1, 2, overflow),
            "max_frame_bytes",
        ),
    )

    # The architecture uses Int64 across languages, so Python's unbounded int
    # must not allow a value another supported runtime cannot represent.
    for limits, field_name in invalid_limits:
        _assert_raises(
            ValueError,
            lambda limits=limits: validate_resource_limits(limits),
            f"{field_name} must fit signed 64-bit range",
        )


def test_resource_limits_validator_rejects_negative_overflow() -> None:
    """Verify values below signed Int64 minimum receive an overflow diagnostic."""
    limits = InteractionResourceLimits(max_frame_bytes=-(1 << 63) - 1)

    # Range validation precedes positivity so a cross-language representation
    # failure remains distinguishable from an ordinary negative limit.
    _assert_raises(
        ValueError,
        lambda: validate_resource_limits(limits),
        "max_frame_bytes must fit signed 64-bit range",
    )


def test_resource_limits_validator_rejects_unsupported_values() -> None:
    """Verify arbitrary objects cannot enter the nominal validation boundary."""
    # Attribute-compatible or unrelated objects have not passed the value-object
    # constructor rules and therefore cannot be treated as resource limits.
    _assert_raises(
        TypeError,
        lambda: validate_resource_limits(cast(InteractionResourceLimits, object())),
        "limits must be InteractionResourceLimits",
    )
