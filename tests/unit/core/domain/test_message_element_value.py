"""Type-boundary tests for generic MessageElementValue data."""

from __future__ import annotations

import json
from typing import assert_type, get_args, get_origin

from mconet.core.domain import JsonValue, MessageElementValue


def _accept_message_element_value(
    value: MessageElementValue,
) -> MessageElementValue:
    """Expose the semantic alias boundary to strict static type checking."""
    # Returning the exact input proves that the alias adds no runtime wrapper,
    # normalization, or ownership behavior to the JSON value carried by an element.
    return value


def test_message_element_value_accepts_complete_json_value_semantics() -> None:
    """Verify every primitive and recursive JSON shape remains expressible."""
    values: tuple[MessageElementValue, ...] = (
        None,
        False,
        42,
        2.5,
        "message value",
        ["ordered", {"nested": True}],
        {"name": "citation", "scores": [1, 0.5]},
    )

    # Each branch crosses the named message boundary unchanged, including JSON
    # null and nested arrays/objects needed by custom message element kinds.
    for value in values:
        assert_type(_accept_message_element_value(value), MessageElementValue)
        assert _accept_message_element_value(value) is value


def test_message_element_value_has_no_non_json_domain_branches() -> None:
    """Verify the alias does not admit binary, tuple, or arbitrary object values."""
    value_branches = frozenset(get_args(MessageElementValue))
    collection_origins = frozenset(
        origin
        for branch in value_branches
        if (origin := get_origin(branch)) is not None
    )

    # Exact equivalence to JsonValue prevents MessageContent, Artifact, Task
    # configuration, callables, bytes, and arbitrary SDK objects from entering
    # the generic field through an additional MessageElementValue union branch.
    assert MessageElementValue is JsonValue
    assert value_branches == frozenset(get_args(JsonValue))
    assert collection_origins == frozenset((list, dict))
    assert bytes not in value_branches
    assert tuple not in value_branches
    assert object not in value_branches


def test_message_element_value_round_trips_without_wrapper_fields() -> None:
    """Verify direct JSON encoding preserves nested element value data."""
    value: MessageElementValue = {
        "unicode": "你好 👋",
        "lines": ["first", "second"],
        "providerData": {"enabled": True, "score": 0.75},
    }

    # Encoding the value itself, rather than a Python-specific wrapper, keeps
    # the language-neutral MessageElement.value wire position stable.
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True)
    decoded: JsonValue = json.loads(encoded)

    assert decoded == value
    # Narrow the decoded JSON union before inspecting object membership; equality
    # alone does not prove the runtime container branch to a static type checker.
    assert isinstance(decoded, dict)
    assert set(decoded) == {"lines", "providerData", "unicode"}
