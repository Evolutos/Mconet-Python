"""Execution-scope tests for the supported unary interaction mode."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal, cast

from mconet.core.domain import (
    ArtifactCatalog,
    Extensions,
    InteractionMode,
    JsonValue,
    ModelDescriptor,
    ModelInteractionError,
    ModelRequest,
    ModelRequestBuilder,
    ModelTarget,
    ModelTaskRequest,
    NamedModel,
    OpenIdentifier,
    TaskDescriptor,
    TaskDocument,
    TaskGroupNode,
    validate_unary_interaction_mode,
)


def _empty_extensions() -> Extensions:
    """Create independent portable mapping storage for test values."""
    # Fresh dictionaries prevent one structural fixture from mutating another
    # task, target, mode, request, or assertion through shared default state.
    return {}


@dataclass(frozen=True, slots=True)
class _Mode:
    """Provide an application-owned open InteractionMode implementation."""

    id: OpenIdentifier
    """Portable standard or provider-defined execution-mode identity."""


@dataclass(frozen=True, slots=True)
class _InvalidModeId:
    """Expose a structurally complete mode with invalid ID storage."""

    id: JsonValue
    """Deliberately non-nominal identifier value used at the trust boundary."""


@dataclass(frozen=True, slots=True)
class _TaskKind:
    """Provide the standard container Kind for an open task document."""

    id: OpenIdentifier
    """Portable task node Kind identity."""

    composition: Literal["leaf", "container"]
    """Task tree composition used by common request validation."""


@dataclass(frozen=True, slots=True)
class _TaskDescriptor:
    """Provide one valid application-owned task descriptor."""

    type: OpenIdentifier
    """Open task identity independent from interaction mode."""

    version: str | None = None
    """Optional producer task contract version."""

    input_schema_id: str | None = None
    """Optional task input schema identity."""

    output_schema_id: str | None = None
    """Optional task output schema identity."""

    metadata: Extensions = field(default_factory=_empty_extensions)
    """Portable descriptor metadata."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Unknown portable descriptor fields."""


@dataclass(frozen=True, slots=True)
class _Task:
    """Provide a complete open ModelTaskRequest for envelope validation."""

    descriptor: TaskDescriptor
    """Task identity and optional schema declarations."""

    document: TaskDocument
    """Versioned task tree independent from interaction mode."""

    artifacts: ArtifactCatalog = field(default_factory=ArtifactCatalog)
    """Concrete request-local Artifact reference scope."""

    metadata: Extensions = field(default_factory=_empty_extensions)
    """Portable task metadata."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Unknown portable task fields."""


@dataclass(frozen=True, slots=True)
class _Target:
    """Provide one complete application-owned ModelTarget."""

    service_id: OpenIdentifier
    """Selected model service identity."""

    protocol_id: OpenIdentifier
    """Selected model protocol identity."""

    model: ModelDescriptor
    """Requested model descriptor."""

    deployment_id: str | None = None
    """Optional provider deployment identity."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Unknown portable routing fields."""


def _task() -> ModelTaskRequest:
    """Create one valid open task request independent from mode selection."""
    # An empty concrete root satisfies the common TaskDocument contract while
    # keeping the mode tests free from conversation-specific node behavior.
    root = TaskGroupNode(
        "root",
        _TaskKind(OpenIdentifier("task.root"), "container"),
        (),
    )
    return _Task(
        descriptor=_TaskDescriptor(OpenIdentifier("vendor.task")),
        document=TaskDocument("1.0", root),
    )


def _target(model_name: str = "fixture-model") -> ModelTarget:
    """Create one valid target with caller-selected model name."""
    # A structural target exercises the open ModelRequest boundary without
    # coupling interaction mode to a concrete service or protocol implementation.
    return _Target(
        service_id=OpenIdentifier("service.vendor"),
        protocol_id=OpenIdentifier("protocol.vendor"),
        model=NamedModel(model_name),
    )


def _request(*, model_name: str = "fixture-model") -> ModelRequest:
    """Build one validated model request for interaction-mode checks."""
    # The public Builder crosses the normal complete request Validator so valid
    # fixtures follow the same domain path used before Runtime support gates.
    return ModelRequestBuilder(_target(model_name), _task()).build()


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> BaseException:
    """Return an expected exception after matching its diagnostic text."""
    # A narrow exception boundary prevents request-fixture setup or protocol
    # recognition failures from satisfying the wrong policy assertion.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return error
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_unary_interaction_mode_accepts_open_mode_by_identity() -> None:
    """Verify a valid unary mode passes unchanged beside a complete request."""
    request = _request()
    mode: InteractionMode = _Mode(OpenIdentifier("unary"))
    original_task = request.task
    original_target = request.target

    # Exact identity proves the gate does not rebuild the open mode or add it to
    # ModelRequest; request-owned target and task values also remain untouched.
    assert validate_unary_interaction_mode(request, mode) is mode
    assert request.target is original_target
    assert request.task is original_task
    assert not hasattr(request, "mode")


def test_unary_interaction_mode_rejects_other_modes_stably() -> None:
    """Verify standard future and unknown modes return one normalized failure."""
    request = _request()
    private_mode = "vendor.private_mode"
    for mode_id in (
        "server_stream",
        "client_stream",
        "duplex",
        "long_running",
        private_mode,
    ):
        mode: InteractionMode = _Mode(OpenIdentifier(mode_id))
        error = cast(
            ModelInteractionError,
            _assert_raises(
                ModelInteractionError,
                lambda mode=mode: validate_unary_interaction_mode(request, mode),
                "Only unary interaction mode is supported",
            ),
        )

        # Every valid unsupported identity receives portable fixed fields without
        # exposing provider-controlled mode text or any request-owned data.
        assert error.category.id == OpenIdentifier("unsupported_feature")
        assert error.phase.id == OpenIdentifier("validation")
        assert error.code == "unsupported_interaction_mode"
        assert error.message == "Only unary interaction mode is supported."
        assert private_mode not in str(error)
        assert request.target.model.name not in str(error)
        assert error.status_code is None
        assert error.service_error_code is None
        assert error.request_id is None
        assert error.recovery is None
        assert error.cause is None


def test_unary_interaction_mode_preserves_request_error_precedence() -> None:
    """Verify malformed requests fail before mode support policy is applied."""
    request = _request()
    object.__setattr__(request.target.model, "name", "")
    unsupported: InteractionMode = _Mode(OpenIdentifier("server_stream"))

    # The preparation chain validates request semantics first, so an invalid model
    # remains an invalid request rather than becoming an unsupported mode error.
    _assert_raises(
        ValueError,
        lambda: validate_unary_interaction_mode(request, unsupported),
        "ModelDescriptor name must not be empty",
    )


def test_unary_interaction_mode_preserves_identifier_error_precedence() -> None:
    """Verify malformed mode identifiers fail before support comparison."""
    request = _request()
    malformed: InteractionMode = _Mode(OpenIdentifier("Invalid Mode"))

    # OpenIdentifier stores raw text; the shared grammar Validator must retain its
    # precise error instead of treating malformed text as a valid unknown mode.
    _assert_raises(
        ValueError,
        lambda: validate_unary_interaction_mode(request, malformed),
        "OpenIdentifier",
    )


def test_unary_interaction_mode_requires_nominal_identifier_storage() -> None:
    """Verify strings and other JSON values cannot substitute for OpenIdentifier."""
    request = _request()
    invalid_values: tuple[JsonValue, ...] = ("unary", 1, True, None, ["unary"])

    for value in invalid_values:
        invalid = cast(InteractionMode, _InvalidModeId(value))
        # Structural mode recognition succeeds because id exists, then the
        # nominal boundary rejects every non-OpenIdentifier representation.
        _assert_raises(
            TypeError,
            lambda invalid=invalid: validate_unary_interaction_mode(request, invalid),
            "InteractionMode id must be an OpenIdentifier",
        )


def test_unary_interaction_mode_requires_complete_protocol() -> None:
    """Verify bare identifiers and unrelated objects fail before support policy."""
    request = _request()

    # Neither a nominal ID nor an arbitrary object implements the complete mode
    # protocol, so the gate rejects both without coercion or string conversion.
    _assert_raises(
        TypeError,
        lambda: validate_unary_interaction_mode(
            request,
            cast(InteractionMode, OpenIdentifier("unary")),
        ),
        "mode must implement InteractionMode",
    )
    _assert_raises(
        TypeError,
        lambda: validate_unary_interaction_mode(
            request,
            cast(InteractionMode, object()),
        ),
        "mode must implement InteractionMode",
    )
