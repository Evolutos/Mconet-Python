"""Canonical equality for decoded JSON fixture values."""

from __future__ import annotations

from typing import cast

from mconet.core.domain import JsonValue, validate_json_value_numbers


def json_fixtures_equal(actual: JsonValue, expected: JsonValue) -> bool:
    """Compare decoded JSON fixtures using language-neutral value semantics.

    Object key order is ignored recursively, while array element order remains
    significant. JSON integers and floating-point values compare as one number
    kind after portable range validation. Booleans remain distinct from numbers
    despite Python's boolean integer subclass relationship.

    Args:
        actual: The decoded fixture value produced by an implementation.
        expected: The decoded fixture value used as the comparison reference.

    Returns:
        ``True`` when both fixtures have the same canonical JSON value.

    Raises:
        TypeError: If either input is not structurally valid JSON data.
        ValueError: If either input contains a non-portable JSON number.
    """
    # Validate both complete inputs before comparison so an invalid fixture is
    # reported as invalid rather than being mistaken for an ordinary mismatch.
    validate_json_value_numbers(actual)
    validate_json_value_numbers(expected)

    # An explicit stack supports deeply nested fixtures without coupling valid
    # fixture depth to Python's recursion limit.
    pending: list[tuple[object, object]] = [(actual, expected)]
    while pending:
        left, right = pending.pop()

        # Containers are matched by their JSON kind. Object key sets are
        # order-independent; array pairs are pushed in their original order.
        if isinstance(left, dict):
            if not isinstance(right, dict) or left.keys() != right.keys():
                return False
            left_mapping = cast(dict[str, object], left)
            right_mapping = cast(dict[str, object], right)
            pending.extend(
                (left_mapping[key], right_mapping[key]) for key in left_mapping
            )
            continue
        if isinstance(left, list):
            if not isinstance(right, list):
                return False
            left_sequence = cast(list[object], left)
            right_sequence = cast(list[object], right)
            if len(left_sequence) != len(right_sequence):
                return False
            pending.extend(zip(left_sequence, right_sequence, strict=True))
            continue

        # bool must be handled before numbers because isinstance(True, int) is
        # true in Python but JSON defines separate boolean and number kinds.
        if isinstance(left, bool):
            if not isinstance(right, bool) or left is not right:
                return False
            continue
        if type(left) in (int, float):
            if type(right) not in (int, float) or left != right:
                return False
            continue
        if left is None:
            if right is not None:
                return False
            continue
        if not isinstance(right, str) or left != right:
            return False

    return True
