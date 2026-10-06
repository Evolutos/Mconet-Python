"""Ordered multi-value tests for immutable QueryParameters."""

from collections.abc import Callable
from dataclasses import FrozenInstanceError
from typing import cast

from mconet.core.domain import QueryParameter, QueryParameters


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    # Check the domain message as well as the exception type so an unrelated
    # implementation failure cannot make the boundary test pass.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_query_parameters_preserve_repeated_names_and_order() -> None:
    """Verify duplicate names remain separate entries in caller order."""
    parameters = (
        QueryParameter("tag", "first"),
        QueryParameter("page", "1"),
        QueryParameter("tag", "second"),
    )
    query = QueryParameters(parameters)

    # Exact tuple retention prevents a mapping conversion from dropping the
    # first duplicate or moving either value during request construction.
    assert query.values == parameters
    assert tuple(item.value for item in query.values if item.name == "tag") == (
        "first",
        "second",
    )


def test_query_parameters_preserve_name_case_and_unencoded_values() -> None:
    """Verify the collection applies no name normalization or URL encoding."""
    query = QueryParameters(
        (
            QueryParameter("Filter", "a/b"),
            QueryParameter("filter", "c+d"),
        )
    )

    # Query names remain distinct by exact spelling, and raw values remain ready
    # for the selected transport to encode once into the final URL.
    assert tuple(item.name for item in query.values) == ("Filter", "filter")
    assert tuple(item.value for item in query.values) == ("a/b", "c+d")


def test_query_parameters_are_immutable() -> None:
    """Verify the record cannot replace its ordered tuple after construction."""
    query = QueryParameters((QueryParameter("page", "1"),))

    # Frozen record storage and the tuple jointly protect both the collection
    # reference and its element order from mutation.
    _assert_raises(
        FrozenInstanceError,
        lambda: query.__setattr__("values", ()),
        "cannot assign to field",
    )
    assert isinstance(query.values, tuple)


def test_query_parameters_reject_invalid_storage() -> None:
    """Verify dynamic callers cannot supply mutable or untyped collections."""
    invalid_collections = (
        lambda: QueryParameters(cast(tuple[QueryParameter, ...], [])),
        lambda: QueryParameters(cast(tuple[QueryParameter, ...], ("value",))),
    )

    # Container and member checks fail at construction, before a transport can
    # observe an unstable order or attempt to encode an arbitrary object.
    for create_query in invalid_collections:
        _assert_raises(TypeError, create_query, "QueryParameters values must")
