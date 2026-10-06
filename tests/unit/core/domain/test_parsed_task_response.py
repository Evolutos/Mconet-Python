"""Ownership and storage-shape tests for ParsedTaskResponse."""

from __future__ import annotations

import inspect
import operator
from collections.abc import Callable, MutableMapping
from dataclasses import FrozenInstanceError, dataclass, fields
from types import MappingProxyType
from typing import Literal, cast

from mconet.core.domain import (
    ArtifactCatalog,
    Extensions,
    JsonValue,
    ModelDescriptor,
    ModelTaskResult,
    NamedModel,
    OpenIdentifier,
    OutputStatus,
    ParsedTaskResponse,
    ProtocolState,
    TaskDescriptor,
    TaskDocument,
    TaskGroupNode,
    TaskNodeKind,
    TokenUsage,
)


@dataclass(frozen=True, slots=True)
class _TaskKind:
    """Provide a complete TaskNodeKind for parsed-result fixtures."""

    id: OpenIdentifier
    """Open task node Kind identifier."""

    composition: Literal["leaf", "container"]
    """Task-tree composition used by the fixture root."""


@dataclass(frozen=True, slots=True)
class _ResultDescriptor:
    """Provide one structurally complete task result descriptor."""

    type: OpenIdentifier
    """Open task result identity."""

    version: str | None
    """Optional task result contract version."""

    input_schema_id: str | None
    """Optional input schema identity retained by the common shape."""

    output_schema_id: str | None
    """Optional result schema identity."""

    metadata: Extensions
    """Portable descriptor metadata."""

    extensions: Extensions
    """Unknown descriptor fields."""


@dataclass(frozen=True, slots=True)
class _TaskResult:
    """Provide an integration-owned ModelTaskResult implementation."""

    descriptor: TaskDescriptor
    """Task result identity and schema contract."""

    document: TaskDocument
    """Versioned result tree."""

    artifacts: ArtifactCatalog
    """Artifact scope owned by this result."""

    metadata: Extensions
    """Portable result metadata."""

    extensions: Extensions
    """Unknown result fields."""


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected storage diagnostic."""
    # Match the field-specific text so an unrelated fixture or assignment error
    # cannot accidentally satisfy a negative response-definition test.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def _result() -> ModelTaskResult:
    """Create one complete task-neutral parsed result fixture."""
    # A custom structural implementation proves ParsedTaskResponse does not bind
    # protocol adapters to a concrete task family or SDK result subclass.
    kind: TaskNodeKind = _TaskKind(OpenIdentifier("task.result_root"), "container")
    descriptor: TaskDescriptor = _ResultDescriptor(
        OpenIdentifier("vendor.document_compare"),
        "1.0",
        None,
        "schema.vendor.result",
        MappingProxyType({}),
        MappingProxyType({}),
    )
    return _TaskResult(
        descriptor,
        TaskDocument("1.0", TaskGroupNode("root", kind, ())),
        ArtifactCatalog(),
        MappingProxyType({}),
        MappingProxyType({}),
    )


def _status(value: str = "completed") -> OutputStatus:
    """Create one open output status for response fixtures."""
    # Use the public value path so tests exercise response ownership rather than
    # bypassing the independently completed OutputStatus contract.
    return OutputStatus(OpenIdentifier(value))


def _state(value: JsonValue = "cursor-2") -> ProtocolState:
    """Create one complete provider protocol-state fixture."""
    # Distinct identifiers make service, protocol, and state type observable as
    # separate response facts rather than one compound implementation detail.
    return ProtocolState(
        OpenIdentifier("vendor.service"),
        OpenIdentifier("vendor.protocol"),
        OpenIdentifier("response.cursor"),
        value,
    )


def test_parsed_task_response_preserves_all_protocol_facts() -> None:
    """Verify every parsed fact remains independent and identity-preserving."""
    result = _result()
    status = _status("requires_action")
    resolved_model: ModelDescriptor = NamedModel("model-actual", version="2026-10")
    usage = TokenUsage(13, 8, 21)
    states = (_state(), _state({"tool_call": "call-7"}))
    response = ParsedTaskResponse(
        result,
        status,
        resolved_model,
        "tool_calls",
        usage,
        states,
        {"vendor.response_id": "response-9"},
    )

    # Exact identities and order prove the envelope carries decoded facts without
    # converting task data, model identity, accounting, or continuation state.
    assert response.result is result
    assert response.status is status
    assert response.resolved_model is resolved_model
    assert response.stop_reason == "tool_calls"
    assert response.usage is usage
    assert response.protocol_state is states
    assert response.protocol_state == states
    assert response.extensions == {"vendor.response_id": "response-9"}


def test_parsed_task_response_preserves_absent_optional_facts() -> None:
    """Verify omitted service facts remain absent instead of being synthesized."""
    result = _result()
    status = _status()
    response = ParsedTaskResponse(result, status)

    # None is authoritative absence: no request target, result descriptor, or
    # status value is copied into fields the service did not report.
    assert response.result is result
    assert response.status is status
    assert response.resolved_model is None
    assert response.stop_reason is None
    assert response.usage is None
    assert response.protocol_state == ()
    assert response.extensions == {}


def test_parsed_task_response_contains_no_runtime_owned_fields() -> None:
    """Verify the envelope surface excludes request and Runtime observations."""
    response_fields = tuple(field.name for field in fields(ParsedTaskResponse))
    constructor_fields = tuple(inspect.signature(ParsedTaskResponse).parameters)

    # The exact public surface contains only architecture-defined protocol facts.
    # Runtime later owns request target restoration and diagnostic aggregation.
    assert response_fields == (
        "result",
        "status",
        "resolved_model",
        "stop_reason",
        "usage",
        "protocol_state",
        "extensions",
    )
    assert constructor_fields == response_fields
    for field_name in (
        "target",
        "diagnostics",
        "request_id",
        "interaction_id",
        "transport",
        "response_metadata",
    ):
        assert not hasattr(ParsedTaskResponse, field_name)


def test_parsed_task_response_is_frozen_and_snapshots_extensions() -> None:
    """Verify response membership cannot change after parsing completes."""
    source: dict[str, JsonValue] = {"vendor.response_id": "response-9"}
    response = ParsedTaskResponse(_result(), _status(), extensions=source)
    source["late"] = True

    # Top-level membership is detached from the parser's mutable source and the
    # frozen envelope prevents replacement of any independently owned fact.
    assert response.extensions == {"vendor.response_id": "response-9"}
    assert "late" not in response.extensions
    _assert_raises(
        FrozenInstanceError,
        lambda: response.__setattr__("stop_reason", "changed"),
        "cannot assign to field",
    )
    _assert_raises(
        TypeError,
        lambda: operator.setitem(
            cast(MutableMapping[str, JsonValue], response.extensions),
            "changed",
            False,
        ),
        "does not support item assignment",
    )


def test_parsed_task_response_definition_defers_nested_semantics() -> None:
    """Verify semantic response checks remain dedicated Validator work."""
    pending_model: ModelDescriptor = NamedModel("")
    pending_json = cast(JsonValue, ("not", "portable"))
    response = ParsedTaskResponse(
        _result(),
        _status(),
        resolved_model=pending_model,
        stop_reason="",
        extensions={"pending": pending_json},
    )

    # Correct storage shapes remain lossless even when nested values need later
    # semantic rejection; definition code neither repairs nor discards evidence.
    assert response.resolved_model is pending_model
    assert response.stop_reason == ""
    assert response.extensions["pending"] is pending_json


def test_parsed_task_response_rejects_invalid_scalar_storage_shapes() -> None:
    """Verify dynamic callers cannot substitute unrelated scalar representations."""
    result = _result()
    status = _status()
    invalid_cases: tuple[tuple[Callable[[], object], str], ...] = (
        (
            lambda: ParsedTaskResponse(cast(ModelTaskResult, object()), status),
            "result must implement ModelTaskResult",
        ),
        (
            lambda: ParsedTaskResponse(
                result,
                cast(OutputStatus, "completed"),
            ),
            "status must be an OutputStatus",
        ),
        (
            lambda: ParsedTaskResponse(
                result,
                status,
                resolved_model=cast(ModelDescriptor, "model"),
            ),
            "resolved_model must implement ModelDescriptor or be None",
        ),
        (
            lambda: ParsedTaskResponse(
                result,
                status,
                stop_reason=cast(str, 7),
            ),
            "stop_reason must be a string or None",
        ),
        (
            lambda: ParsedTaskResponse(
                result,
                status,
                usage=cast(TokenUsage, {}),
            ),
            "usage must be a TokenUsage or None",
        ),
    )

    # Each case crosses static typing deliberately to exercise one runtime field
    # boundary without invoking later semantic validation.
    for action, message in invalid_cases:
        _assert_raises(TypeError, action, message)


def test_parsed_task_response_rejects_invalid_collection_storage_shapes() -> None:
    """Verify state and extension containers have immutable portable membership."""
    result = _result()
    status = _status()
    invalid_cases: tuple[tuple[Callable[[], object], str], ...] = (
        (
            lambda: ParsedTaskResponse(
                result,
                status,
                protocol_state=cast(tuple[ProtocolState, ...], [_state()]),
            ),
            "protocol_state must be a tuple",
        ),
        (
            lambda: ParsedTaskResponse(
                result,
                status,
                protocol_state=cast(tuple[ProtocolState, ...], (object(),)),
            ),
            "protocol_state values must be ProtocolState",
        ),
        (
            lambda: ParsedTaskResponse(
                result,
                status,
                extensions=cast(Extensions, []),
            ),
            "extensions must be a mapping",
        ),
        (
            lambda: ParsedTaskResponse(
                result,
                status,
                extensions=cast(Extensions, {1: True}),
            ),
            "extensions keys must be strings",
        ),
    )

    # Container checks fix only representation and ownership; recursive JSON and
    # cross-field rules remain outside this entity-definition work.
    for action, message in invalid_cases:
        _assert_raises(TypeError, action, message)
