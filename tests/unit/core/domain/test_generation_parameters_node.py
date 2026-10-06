"""Field, ownership, and leaf tests for GenerationParametersNode values."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import FrozenInstanceError
from typing import cast

from mconet.core.domain import (
    Extensions,
    GenerationParameters,
    GenerationParametersNode,
    JsonValue,
    OpenIdentifier,
    TaskNode,
    TaskRelation,
)


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected storage diagnostic."""
    # Match the domain message so an unrelated fixture or assignment error cannot
    # make a negative node-construction test pass accidentally.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def _mutate_mapping(mapping: dict[str, JsonValue]) -> None:
    """Attempt item assignment through a deliberately narrowed mapping type."""
    # Crossing the static read-only boundary proves the runtime proxy enforces
    # ownership after construction rather than relying only on annotations.
    mapping["changed"] = True


def _mutate_kind_id(node: GenerationParametersNode) -> None:
    """Attempt to replace the shared fixed Kind through a low-level setter."""
    # object.__setattr__ bypasses ordinary frozen dataclass guards. The Kind view
    # has no writable storage, so even this path cannot corrupt shared identity.
    object.__setattr__(node.kind, "id", OpenIdentifier("vendor.changed"))


def test_generation_parameters_node_is_fixed_configuration_leaf() -> None:
    """Verify generation controls enter Task through one concrete leaf node."""
    parameters = GenerationParameters(0.7, 0.9, 256, ("done",), 42)
    node = GenerationParametersNode("generation", parameters)
    task_node: TaskNode = node

    # Structural conformance requires no base-class registration. The complete
    # parameter object remains one payload and never becomes task children.
    assert isinstance(node, TaskNode)
    assert task_node.id == "generation"
    assert node.parameters is parameters
    assert node.kind.id == OpenIdentifier("task.configuration")
    assert node.kind.composition == "leaf"
    assert node.children == ()
    assert node.relations == ()
    assert node.metadata == {}
    assert node.extensions == {}

    # The storage-free shared Kind cannot be changed for this or future nodes.
    _assert_raises(AttributeError, lambda: _mutate_kind_id(node), "has no setter")
    assert node.kind.id == OpenIdentifier("task.configuration")


def test_generation_parameters_node_preserves_relations_and_mapping_ownership() -> None:
    """Verify relation order and caller mapping membership remain isolated."""
    first_relation = TaskRelation(
        "generation", "input", OpenIdentifier("task.applies_to")
    )
    second_relation = TaskRelation(
        "generation", "constraint", OpenIdentifier("vendor.precedes")
    )
    metadata: dict[str, JsonValue] = {"source": "client"}
    extensions: dict[str, JsonValue] = {"vendorField": {"enabled": True}}
    node = GenerationParametersNode(
        "generation",
        GenerationParameters(max_output_tokens=128),
        relations=(first_relation, second_relation),
        metadata=metadata,
        extensions=extensions,
    )

    # Relations retain exact objects and order, while top-level caller mutations
    # cannot change either read-only mapping stored by the frozen node.
    metadata["source"] = "changed"
    extensions["other"] = False
    assert node.relations == (first_relation, second_relation)
    assert node.relations[0] is first_relation
    assert node.relations[1] is second_relation
    assert node.metadata == {"source": "client"}
    assert node.extensions == {"vendorField": {"enabled": True}}
    _assert_raises(
        FrozenInstanceError,
        lambda: node.__setattr__("id", "changed"),
        "cannot assign to field",
    )
    _assert_raises(
        TypeError,
        lambda: _mutate_mapping(cast(dict[str, JsonValue], node.metadata)),
        "does not support item assignment",
    )


def test_generation_parameters_node_constructor_exposes_only_owned_fields() -> None:
    """Verify the constructor contains one payload and standard TaskNode fields."""
    constructor_fields = tuple(inspect.signature(GenerationParametersNode).parameters)

    # Kind and children are fixed properties. Message, protocol, access, and
    # individual generation fields cannot bypass the concrete parameters value.
    assert constructor_fields == (
        "id",
        "parameters",
        "relations",
        "metadata",
        "extensions",
    )
    for field_name in (
        "kind",
        "children",
        "messages",
        "temperature",
        "top_p",
        "max_output_tokens",
        "stop",
        "seed",
        "authorization",
        "transport",
    ):
        assert field_name not in constructor_fields


def test_generation_parameters_node_definition_defers_semantic_validation() -> None:
    """Verify node, parameter, relation, and JSON semantics remain deferred."""
    pending_parameters = GenerationParameters(
        temperature=float("inf"),
        max_output_tokens=0,
        stop=("",),
        seed=1 << 80,
    )
    pending_relation = TaskRelation("", "missing", OpenIdentifier("Invalid Relation"))
    pending_json = cast(JsonValue, ("not", "portable"))
    node = GenerationParametersNode(
        "",
        pending_parameters,
        relations=(pending_relation,),
        metadata={"pending": pending_json},
    )

    # Construction preserves source data without normalization. Dedicated node,
    # parameter, and document validators later attribute each semantic failure.
    assert node.id == ""
    assert node.parameters is pending_parameters
    assert node.parameters.temperature == float("inf")
    assert node.parameters.max_output_tokens == 0
    assert node.parameters.stop == ("",)
    assert node.parameters.seed == 1 << 80
    assert node.relations == (pending_relation,)
    assert node.metadata["pending"] is pending_json


def test_generation_parameters_node_requires_concrete_parameters() -> None:
    """Verify a generic mapping cannot replace the concrete task configuration."""
    # A plain object may contain the same field names but lacks the nominal value
    # semantics and dedicated validation boundary required by this node.
    _assert_raises(
        TypeError,
        lambda: GenerationParametersNode(
            "generation",
            cast(GenerationParameters, {"temperature": 0.7}),
        ),
        "parameters must be GenerationParameters",
    )


def test_generation_parameters_node_rejects_invalid_storage_shapes() -> None:
    """Verify dynamic callers cannot bypass immutable field contracts."""
    parameters = GenerationParameters()
    relation = TaskRelation("generation", "input", OpenIdentifier("task.applies_to"))
    invalid_cases: tuple[tuple[Callable[[], object], str], ...] = (
        (
            lambda: GenerationParametersNode(cast(str, 1), parameters),
            "id must be a string",
        ),
        (
            lambda: GenerationParametersNode(
                "generation",
                parameters,
                relations=cast(tuple[TaskRelation, ...], [relation]),
            ),
            "relations must be a tuple",
        ),
        (
            lambda: GenerationParametersNode(
                "generation",
                parameters,
                relations=cast(tuple[TaskRelation, ...], (object(),)),
            ),
            "relations must contain TaskRelation values",
        ),
        (
            lambda: GenerationParametersNode(
                "generation", parameters, metadata=cast(Extensions, [])
            ),
            "metadata must be a mapping",
        ),
        (
            lambda: GenerationParametersNode(
                "generation",
                parameters,
                metadata=cast(Extensions, {1: True}),
            ),
            "metadata keys must be strings",
        ),
        (
            lambda: GenerationParametersNode(
                "generation",
                parameters,
                extensions=cast(Extensions, "invalid"),
            ),
            "extensions must be a mapping",
        ),
    )

    # Each case changes one storage boundary only; all semantic rules remain
    # deferred to the following validation layer.
    for action, message in invalid_cases:
        _assert_raises(TypeError, action, message)
