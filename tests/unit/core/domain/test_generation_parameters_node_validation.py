"""Semantic validation tests for GenerationParametersNode values."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from math import inf
from typing import Literal, cast

from mconet.core.domain import (
    GenerationParameters,
    GenerationParametersNode,
    JsonValue,
    OpenIdentifier,
    TaskDocument,
    TaskGroupNode,
    TaskNodeKind,
    TaskRelation,
    validate_generation_parameters_node,
    validate_task_document,
)


@dataclass(frozen=True, slots=True)
class _TaskKind:
    """Provide alternate TaskNodeKind values for validation fixtures."""

    id: OpenIdentifier
    """Candidate configuration or root Kind identity."""

    composition: Literal["leaf", "container"]
    """Candidate node composition checked by shared and concrete rules."""


_WRONG_ID_KIND: TaskNodeKind = _TaskKind(
    OpenIdentifier("vendor.parameters"),
    "leaf",
)
_WRONG_COMPOSITION_KIND: TaskNodeKind = _TaskKind(
    OpenIdentifier("task.configuration"),
    "container",
)


class _WrongIdNode(GenerationParametersNode):
    """Override only the fixed Kind identity on a concrete node subclass."""

    __slots__ = ()

    @property
    def kind(self) -> TaskNodeKind:
        """Return a portable but nonstandard parameter node Kind."""
        # The alternate leaf reaches the concrete exact-ID rule after all shared
        # TaskNode Kind checks have succeeded.
        return _WRONG_ID_KIND


class _WrongCompositionNode(GenerationParametersNode):
    """Override only the fixed composition on a concrete node subclass."""

    __slots__ = ()

    @property
    def kind(self) -> TaskNodeKind:
        """Return the standard identity with invalid container composition."""
        # Empty children make the generic container structurally valid, isolating
        # this concrete node's required leaf diagnostic.
        return _WRONG_COMPOSITION_KIND


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected type and diagnostic fragment."""
    # A narrow boundary ensures an unrelated fixture error cannot satisfy a
    # node- or parameter-specific validation expectation accidentally.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def _root(*children: GenerationParametersNode) -> TaskGroupNode:
    """Create the standard task root around parameter node children."""
    # Exact child objects pass through unchanged so document integration observes
    # the same parameter payload used by direct node validation.
    return TaskGroupNode(
        "root",
        _TaskKind(OpenIdentifier("task.root"), "container"),
        children,
    )


def _overwrite_parameters(node: GenerationParametersNode, value: object) -> None:
    """Replace the frozen parameter field to emulate untyped deserialization."""
    # Constructor invariants normally prevent this state; object-level assignment
    # proves the Validator rechecks concrete payload presence at runtime.
    object.__setattr__(node, "parameters", value)


def test_validator_accepts_valid_node_and_preserves_parameter_value() -> None:
    """Verify successful validation returns the original node and payload."""
    parameters = GenerationParameters(0.7, 0.9, 256, ("done",), 42)
    node = GenerationParametersNode("generation", parameters)

    # Shared TaskNode and nested parameter validation are observational; neither
    # rebuilds, normalizes, or replaces the immutable values.
    assert validate_generation_parameters_node(node) is node
    assert node.parameters is parameters
    assert node.kind.id == OpenIdentifier("task.configuration")
    assert node.kind.composition == "leaf"
    assert node.children == ()


def test_validator_rejects_non_parameter_node_before_field_access() -> None:
    """Verify unrelated objects cannot acquire generation node semantics."""
    _assert_raises(
        TypeError,
        lambda: validate_generation_parameters_node(
            cast(GenerationParametersNode, object())
        ),
        "must be a GenerationParametersNode",
    )


def test_validator_delegates_shared_task_node_rules() -> None:
    """Verify common node identity, relation, and JSON rules remain centralized."""
    invalid_relation = TaskRelation(
        "",
        "target",
        OpenIdentifier("task.references"),
    )
    invalid_json = GenerationParametersNode(
        "generation",
        GenerationParameters(),
        metadata={"invalid": cast(JsonValue, ("tuple",))},
    )

    # The shared TaskNode snapshot runs before concrete payload inspection so all
    # node types receive one stable implementation of common diagnostics.
    _assert_raises(
        ValueError,
        lambda: validate_generation_parameters_node(
            GenerationParametersNode("", GenerationParameters())
        ),
        "id must not be empty",
    )
    _assert_raises(
        ValueError,
        lambda: validate_generation_parameters_node(
            GenerationParametersNode(
                "generation",
                GenerationParameters(),
                relations=(invalid_relation,),
            )
        ),
        "source must not be empty",
    )
    _assert_raises(
        TypeError,
        lambda: validate_generation_parameters_node(invalid_json),
        "JsonValue",
    )


def test_validator_enforces_fixed_kind_identity_and_leaf_composition() -> None:
    """Verify concrete subclasses cannot reclassify the parameter node."""
    wrong_id = _WrongIdNode("generation", GenerationParameters())
    wrong_composition = _WrongCompositionNode("generation", GenerationParameters())

    # Generic TaskNode validation accepts both portable alternate Kinds; the
    # concrete Validator adds this node type's exact identity and leaf rule.
    _assert_raises(
        ValueError,
        lambda: validate_generation_parameters_node(wrong_id),
        "kind id must be task.configuration",
    )
    _assert_raises(
        ValueError,
        lambda: validate_generation_parameters_node(wrong_composition),
        "kind composition must be leaf",
    )


def test_validator_rejects_missing_or_wrong_parameter_value() -> None:
    """Verify dynamically absent and generic mapping payloads fail stably."""
    missing = GenerationParametersNode("generation", GenerationParameters())
    wrong = GenerationParametersNode("generation", GenerationParameters())
    _overwrite_parameters(missing, None)
    _overwrite_parameters(wrong, {"temperature": 0.7})

    # Both corrupted values bypass construction, proving validation requires the
    # nominal immutable GenerationParameters rather than mapping shape or truth.
    for node in (missing, wrong):
        _assert_raises(
            TypeError,
            lambda node=node: validate_generation_parameters_node(node),
            "parameters must be GenerationParameters",
        )


def test_validator_delegates_every_generation_parameter_rule() -> None:
    """Verify nested field failures retain their parameter diagnostics."""
    malformed: tuple[tuple[GenerationParameters, str], ...] = (
        (GenerationParameters(temperature=inf), "temperature must be finite"),
        (GenerationParameters(top_p=1.1), "top_p must be between 0 and 1"),
        (
            GenerationParameters(max_output_tokens=0),
            "max_output_tokens must be positive",
        ),
        (GenerationParameters(stop=("",)), "stop sequence at index 0"),
        (GenerationParameters(seed=2**53), "seed must be within"),
    )

    # The Task wrapper does not translate or duplicate generation rules; the
    # nested Validator remains the single owner of every field diagnostic.
    for parameters, message in malformed:
        node = GenerationParametersNode("generation", parameters)
        _assert_raises(
            ValueError,
            lambda node=node: validate_generation_parameters_node(node),
            message,
        )


def test_task_document_validation_dispatches_parameter_payload_rules() -> None:
    """Verify whole-task traversal validates known concrete parameter leaves."""
    valid = GenerationParametersNode(
        "valid-parameters",
        GenerationParameters(max_output_tokens=128),
    )
    invalid = GenerationParametersNode(
        "invalid-parameters",
        GenerationParameters(max_output_tokens=0),
    )

    # TaskDocument already owns stable snapshots and invokes only known concrete
    # payload rules, while provider-defined TaskNode implementations remain open.
    assert validate_task_document(TaskDocument("1.0", _root(valid))) is not None
    _assert_raises(
        ValueError,
        lambda: validate_task_document(TaskDocument("1.0", _root(invalid))),
        "max_output_tokens must be positive",
    )
