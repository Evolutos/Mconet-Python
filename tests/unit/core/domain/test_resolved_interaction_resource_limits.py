"""Completeness tests for immutable ResolvedInteractionResourceLimits."""

import math
from collections.abc import Callable
from dataclasses import FrozenInstanceError
from inspect import Parameter, signature
from typing import cast

from mconet.core.domain import ResolvedInteractionResourceLimits


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    # Match a stable diagnostic fragment so an unrelated constructor failure
    # cannot make an invalid resolved-limit test pass accidentally.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_resolved_interaction_resource_limits_require_every_field() -> None:
    """Verify construction cannot omit any resolved byte limit."""
    constructor_parameters = signature(ResolvedInteractionResourceLimits).parameters
    expected_fields = (
        "max_response_body_bytes",
        "max_streaming_error_body_bytes",
        "max_frame_bytes",
    )

    # A complete ordered signature prevents resolution from representing an
    # implicit or unlimited field by omitting it or relying on a default.
    assert tuple(constructor_parameters) == expected_fields
    for field_name in expected_fields:
        assert constructor_parameters[field_name].default is Parameter.empty


def test_resolved_interaction_resource_limits_preserve_complete_input() -> None:
    """Verify all resolved byte limits retain their exact integer values."""
    limits = ResolvedInteractionResourceLimits(
        max_response_body_bytes=16_777_216,
        max_streaming_error_body_bytes=1_048_576,
        max_frame_bytes=2_097_152,
    )

    # The resolved value stores one explicit limit per consumer without unit
    # conversion or cross-field inference.
    assert limits.max_response_body_bytes == 16_777_216
    assert limits.max_streaming_error_body_bytes == 1_048_576
    assert limits.max_frame_bytes == 2_097_152


def test_resolved_interaction_resource_limits_reject_unbounded_values() -> None:
    """Verify no field accepts absence or a floating-point infinity sentinel."""
    invalid_limits = (
        lambda: ResolvedInteractionResourceLimits(
            cast(int, None),
            20,
            30,
        ),
        lambda: ResolvedInteractionResourceLimits(
            10,
            cast(int, math.inf),
            30,
        ),
        lambda: ResolvedInteractionResourceLimits(
            10,
            20,
            cast(int, -math.inf),
        ),
    )

    # None and infinity are common unbounded representations; rejecting both
    # makes every resolved consumer operate on a concrete finite byte count.
    for create_limits in invalid_limits:
        _assert_raises(TypeError, create_limits, "must be an integer")


def test_resolved_interaction_resource_limits_reject_non_integer_storage() -> None:
    """Verify booleans, finite floats, and numeric strings are not byte limits."""
    invalid_limits = (
        lambda: ResolvedInteractionResourceLimits(cast(int, True), 20, 30),
        lambda: ResolvedInteractionResourceLimits(10, cast(int, 20.0), 30),
        lambda: ResolvedInteractionResourceLimits(10, 20, cast(int, "30")),
    )

    # Exact integer storage prevents permissive coercion from changing caller
    # configuration before semantic validation reports range errors.
    for create_limits in invalid_limits:
        _assert_raises(TypeError, create_limits, "must be an integer")


def test_resolved_interaction_resource_limits_defer_semantic_number_rules() -> None:
    """Verify integer range errors remain available to the later validator."""
    limits = ResolvedInteractionResourceLimits(0, -1, 1 << 63)

    # Completeness and finiteness are structural requirements. The dedicated
    # validator owns positive-value and signed 64-bit diagnostics.
    assert limits.max_response_body_bytes == 0
    assert limits.max_streaming_error_body_bytes == -1
    assert limits.max_frame_bytes == 1 << 63


def test_resolved_interaction_resource_limits_have_value_semantics() -> None:
    """Verify equality, hashing, and immutability include every resolved field."""
    first = ResolvedInteractionResourceLimits(10, 20, 30)
    same = ResolvedInteractionResourceLimits(10, 20, 30)
    different = ResolvedInteractionResourceLimits(10, 20, 31)

    # Frozen value semantics allow one resolved instance to be shared by the
    # transport, error collector, and framer without consumer mutation.
    assert first == same
    assert hash(first) == hash(same)
    assert first != different
    _assert_raises(
        FrozenInstanceError,
        lambda: first.__setattr__("max_frame_bytes", 40),
        "cannot assign to field",
    )
