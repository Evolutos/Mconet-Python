"""Semantic validation for generation parameter task configuration leaves."""

from __future__ import annotations

from typing import cast

from mconet.core.domain.generation_parameters import GenerationParameters
from mconet.core.domain.generation_parameters_node import GenerationParametersNode
from mconet.core.domain.generation_parameters_validation import (
    validate_generation_parameters,
)
from mconet.core.domain.task_node_validation import validate_task_node_snapshot


def validate_generation_parameters_node(
    node: GenerationParametersNode,
) -> GenerationParametersNode:
    """Validate one parameter leaf and its complete generation controls.

    Args:
        node: The concrete immutable generation parameter node to validate.

    Returns:
        The same node object after successful validation.

    Raises:
        TypeError: If the node, shared TaskNode fields, or ``parameters`` has an
            invalid runtime type.
        ValueError: If task leaf semantics, node data, or a generation field
            violates its domain contract.

    Notes:
        Task relation endpoint resolution and document-wide node ID uniqueness
        remain owned by TaskDocument validation. This function fully validates
        GenerationParameters because they are the node's concrete payload.
    """
    candidate = cast(object, node)
    # Require the nominal leaf before shared structural validation so unrelated
    # custom configuration nodes cannot acquire generation parameter semantics.
    if not isinstance(candidate, GenerationParametersNode):
        raise TypeError("node must be a GenerationParametersNode.")

    validated_node, _, _ = validate_task_node_snapshot(candidate)
    # Shared validation returns its protocol type but preserves object identity;
    # the nominal check above therefore justifies restoring the concrete type.
    validated = cast(GenerationParametersNode, validated_node)
    validate_generation_parameters_node_fields(validated)
    return validated


def validate_generation_parameters_node_fields(
    node: GenerationParametersNode,
) -> None:
    """Validate fixed Kind and parameter fields after shared node validation."""
    kind = node.kind
    # The shared validator already narrowed Kind fields and portable syntax. This
    # concrete node adds its exact configuration identity without a type registry.
    if kind.id.value != "task.configuration":
        raise ValueError("GenerationParametersNode kind id must be task.configuration.")
    if kind.composition != "leaf":
        raise ValueError("GenerationParametersNode kind composition must be leaf.")

    parameters = cast(object, node.parameters)
    # Recheck required payload presence in case an untyped deserializer bypasses
    # the frozen constructor and inserts None, a mapping, or another domain value.
    if not isinstance(parameters, GenerationParameters):
        raise TypeError(
            "GenerationParametersNode parameters must be GenerationParameters."
        )

    # Delegate numeric, probability, token, stop, seed, and portability rules to
    # the parameter domain so node validation never duplicates field semantics.
    validate_generation_parameters(parameters)
