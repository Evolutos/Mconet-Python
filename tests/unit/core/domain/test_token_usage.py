"""Value, omission, and extension tests for TokenUsage."""

from __future__ import annotations

import math
import operator
from collections.abc import Callable, MutableMapping
from dataclasses import FrozenInstanceError, fields
from typing import cast

from mconet.core.domain import Extensions, JsonValue, TokenUsage

_MAX_SAFE_INTEGER = 2**53 - 1


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    # Stable exception and message checks distinguish field-specific validation
    # from incidental failures in dataclass or mapping machinery.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_token_usage_preserves_missing_counts_without_forging_zero() -> None:
    """Verify every omitted provider count remains independently absent."""
    usage = TokenUsage()

    # Missing response fields are facts distinct from an explicit zero-token
    # report, and the default provider extension object is concretely empty.
    assert usage.input_tokens is None
    assert usage.output_tokens is None
    assert usage.total_tokens is None
    assert usage.extensions == {}
    assert not hasattr(usage.extensions, "__setitem__")


def test_token_usage_preserves_explicit_counts_and_independent_total() -> None:
    """Verify component and total counts retain exact provider-reported values."""
    usage = TokenUsage(input_tokens=11, output_tokens=7, total_tokens=25)

    # Total may include provider-specific categories and therefore remains 25
    # rather than being normalized to the arithmetic component sum of 18.
    assert usage.input_tokens == 11
    assert usage.output_tokens == 7
    assert usage.total_tokens == 25
    assert usage.total_tokens != usage.input_tokens + usage.output_tokens


def test_token_usage_distinguishes_zero_from_absent_fields() -> None:
    """Verify explicit zero counts do not collapse into missing values."""
    usage = TokenUsage(input_tokens=0, output_tokens=None, total_tokens=0)

    # Zero is a valid concrete service report, while None means that output usage
    # was not present and must not be synthesized by response mapping.
    assert usage.input_tokens == 0
    assert usage.output_tokens is None
    assert usage.total_tokens == 0


def test_token_usage_snapshots_portable_provider_extensions() -> None:
    """Verify recursive provider breakdowns remain exact and outer membership freezes."""
    source: dict[str, JsonValue] = {
        "cached_input_tokens": 3,
        "reasoning": {"tokens": 5, "estimated": False},
    }
    usage = TokenUsage(11, 7, 25, source)
    source["later"] = 99

    # Top-level copying detaches later caller insertions while retaining exact
    # nested JSON values and producer-specific names without interpretation.
    assert usage.extensions == {
        "cached_input_tokens": 3,
        "reasoning": {"tokens": 5, "estimated": False},
    }
    assert "later" not in usage.extensions
    _assert_raises(
        TypeError,
        lambda: operator.setitem(
            cast(MutableMapping[str, JsonValue], usage.extensions), "x", 1
        ),
        "does not support item assignment",
    )


def test_token_usage_has_frozen_complete_field_semantics() -> None:
    """Verify equality, field ownership, and immutability cover the full value."""
    first = TokenUsage(1, 2, 3, {"provider": "a"})
    same = TokenUsage(1, 2, 3, {"provider": "a"})
    different = TokenUsage(1, 2, None, {"provider": "a"})

    # All four owned fields participate in value equality, and frozen storage
    # prevents replacing any count after a response has been parsed.
    assert first == same
    assert first != different
    assert tuple(field.name for field in fields(TokenUsage)) == (
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "extensions",
    )
    _assert_raises(
        FrozenInstanceError,
        lambda: first.__setattr__("total_tokens", 4),
        "cannot assign to field",
    )


def test_token_usage_rejects_non_integer_count_storage() -> None:
    """Verify booleans, floats, text, and objects cannot masquerade as counts."""
    invalid_values = (True, 1.0, "1", object())

    # Exercise each standard position while crossing static typing deliberately;
    # exact runtime membership must reject every coercible alternate shape.
    for value in invalid_values:
        _assert_raises(
            TypeError,
            lambda value=value: TokenUsage(input_tokens=cast(int, value)),
            "input_tokens must be an integer or None",
        )
        _assert_raises(
            TypeError,
            lambda value=value: TokenUsage(output_tokens=cast(int, value)),
            "output_tokens must be an integer or None",
        )
        _assert_raises(
            TypeError,
            lambda value=value: TokenUsage(total_tokens=cast(int, value)),
            "total_tokens must be an integer or None",
        )


def test_token_usage_rejects_negative_and_unsafe_counts() -> None:
    """Verify counts remain non-negative and exactly portable through JSON."""
    for field_name, create_usage in (
        ("input_tokens", lambda: TokenUsage(input_tokens=-1)),
        ("output_tokens", lambda: TokenUsage(output_tokens=-1)),
        ("total_tokens", lambda: TokenUsage(total_tokens=-1)),
    ):
        _assert_raises(
            ValueError,
            create_usage,
            f"{field_name} must not be negative",
        )

    # The maximum interoperable JSON integer is accepted exactly; its successor
    # fails instead of being rounded by a binary64-based consumer.
    assert TokenUsage(total_tokens=_MAX_SAFE_INTEGER).total_tokens == _MAX_SAFE_INTEGER
    _assert_raises(
        ValueError,
        lambda: TokenUsage(total_tokens=_MAX_SAFE_INTEGER + 1),
        "interoperable safe range",
    )


def test_token_usage_rejects_invalid_extension_containers_and_keys() -> None:
    """Verify provider extension storage is a string-keyed Mapping."""
    _assert_raises(
        TypeError,
        lambda: TokenUsage(extensions=cast(Extensions, [])),
        "extensions must be a mapping",
    )
    _assert_raises(
        TypeError,
        lambda: TokenUsage(extensions=cast(Extensions, {1: "invalid"})),
        "extensions keys must be strings",
    )


def test_token_usage_rejects_nonportable_extension_values() -> None:
    """Verify provider data obeys recursive JSON shape and number rules."""
    invalid_cases = (
        (
            cast(Extensions, {"value": object()}),
            TypeError,
            "structurally valid JsonValue",
        ),
        (
            cast(Extensions, {"value": math.inf}),
            ValueError,
            "must be finite",
        ),
        (
            cast(Extensions, {"value": _MAX_SAFE_INTEGER + 1}),
            ValueError,
            "interoperable safe range",
        ),
    )

    # Delegate each recursive value to the shared JSON contract so usage-specific
    # extensions cannot introduce host objects or non-interoperable numbers.
    for extensions, error_type, message in invalid_cases:
        _assert_raises(
            error_type,
            lambda extensions=extensions: TokenUsage(extensions=extensions),
            message,
        )
