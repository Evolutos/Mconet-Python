"""Optional-field tests for immutable InteractionResourceLimits."""

from collections.abc import Callable
from dataclasses import FrozenInstanceError
from typing import cast

from mconet.core.domain import InteractionResourceLimits


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    # Match the stable field diagnostic so an unrelated constructor exception
    # cannot make a negative resource-limit test pass accidentally.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_interaction_resource_limits_allow_every_field_to_be_omitted() -> None:
    """Verify unresolved input can leave all byte limits unspecified."""
    limits = InteractionResourceLimits()

    # None retains the distinction between an absent override and a numeric
    # value that a later resolver must merge with lower-priority defaults.
    assert limits.max_response_body_bytes is None
    assert limits.max_streaming_error_body_bytes is None
    assert limits.max_frame_bytes is None


def test_interaction_resource_limits_preserve_independent_overrides() -> None:
    """Verify each optional limit can be supplied without filling the others."""
    response_only = InteractionResourceLimits(max_response_body_bytes=16_777_216)
    streaming_error_only = InteractionResourceLimits(
        max_streaming_error_body_bytes=1_048_576
    )
    frame_only = InteractionResourceLimits(max_frame_bytes=2_097_152)

    # Per-field independence is required for later layer-by-layer merging; no
    # constructor path infers one limit from another.
    assert response_only == InteractionResourceLimits(16_777_216, None, None)
    assert streaming_error_only == InteractionResourceLimits(None, 1_048_576, None)
    assert frame_only == InteractionResourceLimits(None, None, 2_097_152)


def test_interaction_resource_limits_preserve_complete_input() -> None:
    """Verify all supplied byte limits retain their exact integer values."""
    limits = InteractionResourceLimits(
        max_response_body_bytes=16_777_216,
        max_streaming_error_body_bytes=1_048_576,
        max_frame_bytes=2_097_152,
    )

    # The unresolved value object stores caller input without unit conversion,
    # default substitution, or cross-field normalization.
    assert limits.max_response_body_bytes == 16_777_216
    assert limits.max_streaming_error_body_bytes == 1_048_576
    assert limits.max_frame_bytes == 2_097_152


def test_interaction_resource_limits_defer_semantic_number_rules() -> None:
    """Verify semantic invalid integers remain available to the later validator."""
    limits = InteractionResourceLimits(
        max_response_body_bytes=0,
        max_streaming_error_body_bytes=-1,
        max_frame_bytes=1 << 63,
    )

    # Construction enforces storage only. A subsequent dedicated validator owns
    # positive-value and signed 64-bit overflow diagnostics.
    assert limits.max_response_body_bytes == 0
    assert limits.max_streaming_error_body_bytes == -1
    assert limits.max_frame_bytes == 1 << 63


def test_interaction_resource_limits_have_immutable_value_semantics() -> None:
    """Verify equality, hashing, and immutability include every optional field."""
    first = InteractionResourceLimits(10, 20, 30)
    same = InteractionResourceLimits(10, 20, 30)
    different = InteractionResourceLimits(10, 20, None)

    # Frozen value semantics make unresolved limits safe to reuse across
    # interactions without one resolution pass mutating client defaults.
    assert first == same
    assert hash(first) == hash(same)
    assert first != different
    _assert_raises(
        FrozenInstanceError,
        lambda: first.__setattr__("max_frame_bytes", 40),
        "cannot assign to field",
    )


def test_interaction_resource_limits_reject_non_integer_storage() -> None:
    """Verify supplied values cannot use floats, booleans, or numeric strings."""
    invalid_limits = (
        lambda: InteractionResourceLimits(max_response_body_bytes=cast(int, 1.0)),
        lambda: InteractionResourceLimits(
            max_streaming_error_body_bytes=cast(int, True)
        ),
        lambda: InteractionResourceLimits(max_frame_bytes=cast(int, "1024")),
    )

    # Every field is checked at construction so later merging sees only exact
    # optional integers even though semantic range validation is deferred.
    for create_limits in invalid_limits:
        _assert_raises(TypeError, create_limits, "must be an integer or None")
