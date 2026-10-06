"""Value-contract tests for immutable QueryParameter records."""

from collections.abc import Callable
from dataclasses import FrozenInstanceError
from typing import cast

from mconet.core.domain import QueryParameter


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    # Match the stable domain message so a different failure cannot satisfy the
    # negative test accidentally.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_query_parameter_preserves_unencoded_text() -> None:
    """Verify construction does not percent-encode or normalize either field."""
    parameter = QueryParameter("filter name", "a/b + c&d")

    # Transport receives the original components and therefore remains the
    # single owner of URL encoding and query-string assembly.
    assert parameter.name == "filter name"
    assert parameter.value == "a/b + c&d"


def test_query_parameter_is_immutable_and_has_value_equality() -> None:
    """Verify equal pairs compare by fields and cannot be reassigned."""
    first = QueryParameter("page", "1")
    same = QueryParameter("page", "1")

    # Frozen records can be shared by later ordered collections without the
    # source name or value changing between planning and transport.
    assert first == same
    _assert_raises(
        FrozenInstanceError,
        lambda: first.__setattr__("value", "2"),
        "cannot assign to field",
    )


def test_query_parameter_rejects_non_string_storage() -> None:
    """Verify dynamic callers cannot bypass the primitive field contract."""
    invalid_parameters = (
        lambda: QueryParameter(cast(str, 1), "value"),
        lambda: QueryParameter("name", cast(str, b"value")),
    )

    # Reject invalid storage at construction so no transport encounters a value
    # it cannot encode according to its own query rules.
    for create_parameter in invalid_parameters:
        _assert_raises(TypeError, create_parameter, "must be a string")
