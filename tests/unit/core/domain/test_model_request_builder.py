"""Tests for fluent construction of immutable model interaction requests."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import FrozenInstanceError, dataclass, field
from typing import Literal, cast

import mconet.core.domain
import mconet.core.domain.model_request_builder as builder_module
from mconet.core.domain import (
    ArtifactCatalog,
    Extensions,
    Headers,
    JsonValue,
    ModelRequest,
    ModelRequestBuilder,
    ModelTarget,
    ModelTaskRequest,
    NamedModel,
    OpenIdentifier,
    QueryParameters,
    ServiceAccess,
    TaskDescriptor,
    TaskDocument,
    TaskGroupNode,
    TaskNodeKind,
    UriValue,
    validate_model_request,
)


def _empty_extensions() -> Extensions:
    """Create independently owned extension storage for test fixtures."""
    # Fresh dictionaries prevent structural fixture instances from sharing
    # mutable unknown-field state through dataclass defaults.
    return {}


@dataclass(frozen=True, slots=True)
class _TaskKind:
    """Provide a complete root task Kind for open task fixtures."""

    id: OpenIdentifier
    """Open task node classification identity."""

    composition: Literal["leaf", "container"]
    """Tree composition consumed by task document validation."""


@dataclass(frozen=True, slots=True)
class _Descriptor:
    """Provide one complete descriptor for an application-owned task."""

    type: OpenIdentifier
    """Open task family identity."""

    version: str | None = None
    """Optional task contract version."""

    input_schema_id: str | None = None
    """Optional external input schema identity."""

    output_schema_id: str | None = None
    """Optional external output schema identity."""

    metadata: Extensions = field(default_factory=_empty_extensions)
    """Portable descriptor metadata."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Unknown descriptor fields retained without interpretation."""


@dataclass(frozen=True, slots=True)
class _Task:
    """Provide an open non-conversation task request for Builder tests."""

    descriptor: TaskDescriptor
    """Open task identity and schema contract."""

    document: TaskDocument
    """Versioned task input and configuration tree."""

    artifacts: ArtifactCatalog
    """Request-local Artifact reference scope."""

    metadata: Extensions = field(default_factory=_empty_extensions)
    """Portable task metadata."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Unknown task fields retained without interpretation."""


@dataclass(frozen=True, slots=True)
class _Target:
    """Provide an open model target for Builder tests."""

    service_id: OpenIdentifier
    """Selected model service identity."""

    protocol_id: OpenIdentifier
    """Selected protocol identity."""

    model: NamedModel
    """Selected provider-facing model descriptor."""

    deployment_id: str | None = None
    """Optional service deployment identity."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Unknown target fields retained without interpretation."""


@dataclass(frozen=True, slots=True)
class _Access:
    """Provide complete unresolved service access without authorization."""

    endpoint: UriValue | None
    """Optional endpoint URI supplied by this request layer."""

    authorization: None = None
    """Explicitly unresolved authorization input."""

    headers: Headers = field(default_factory=Headers)
    """Ordered non-sensitive custom request headers."""

    query: QueryParameters = field(default_factory=QueryParameters)
    """Ordered non-sensitive custom query parameters."""

    api_version: str | None = None
    """Optional provider API version context."""

    project_id: str | None = None
    """Optional provider project context."""

    tenant_id: str | None = None
    """Optional provider tenant context."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Unknown access fields retained without interpretation."""


@dataclass(frozen=True, slots=True)
class _IncompleteTarget:
    """Expose only target service identity for negative storage testing."""

    service_id: OpenIdentifier
    """One field cannot satisfy the complete ModelTarget protocol."""


@dataclass(frozen=True, slots=True)
class _IncompleteTask:
    """Expose only a descriptor for negative storage testing."""

    descriptor: TaskDescriptor
    """One field cannot satisfy the complete ModelTaskRequest protocol."""


@dataclass(frozen=True, slots=True)
class _IncompleteAccess:
    """Expose only an endpoint for negative storage testing."""

    endpoint: UriValue | None
    """One field cannot satisfy the complete ServiceAccess protocol."""


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> BaseException:
    """Return the expected exception after matching its diagnostic fragment."""
    # Keep the exception boundary narrow so unrelated fixture or assertion
    # failures cannot accidentally satisfy a negative Builder scenario.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return error
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def _target(*, service_id: str = "service.vendor") -> ModelTarget:
    """Create one complete structural model target."""
    # Distinct service and protocol IDs prove neither is inferred from the model
    # name or merged with the optional deployment identity.
    return _Target(
        OpenIdentifier(service_id),
        OpenIdentifier("protocol.vendor"),
        NamedModel("vendor-model"),
        "primary",
        {"routingHint": "east"},
    )


def _task() -> ModelTaskRequest:
    """Create one semantically valid application-owned open task request."""
    # A non-conversation descriptor demonstrates that the Builder stays task
    # neutral while the complete common task boundary remains validator-owned.
    kind: TaskNodeKind = _TaskKind(OpenIdentifier("task.root"), "container")
    descriptor: TaskDescriptor = _Descriptor(
        OpenIdentifier("vendor.document_compare"),
        version="2026.10",
        metadata={"owner": "application"},
    )
    return _Task(
        descriptor,
        TaskDocument("1.0", TaskGroupNode("root", kind, ())),
        ArtifactCatalog(),
        metadata={"taskLabel": "comparison"},
    )


def _access(endpoint: str = "https://models.example.test/v1") -> ServiceAccess:
    """Create one complete request-level service access override."""
    # Access remains independent from routing identity and deliberately leaves
    # authorization absent for later configuration resolution.
    return _Access(
        endpoint=UriValue(endpoint, is_absolute=True),
        api_version="2026-10-01",
        project_id="project-a",
        tenant_id="tenant-a",
        extensions={"accessOption": True},
    )


def _mutate_mapping(mapping: dict[str, JsonValue]) -> None:
    """Attempt item assignment through a deliberately narrowed mapping type."""
    # Static narrowing crosses the read-only annotation solely to prove that the
    # concrete output proxy also rejects mutation at runtime.
    mapping["changed"] = True


def _mutate_request(request: ModelRequest, target: ModelTarget) -> None:
    """Attempt ordinary assignment through the private frozen concrete value."""
    # Calling the generated frozen setter proves immutability without importing
    # or exposing the private implementation class as public API.
    request.__setattr__("target", target)


def test_builder_creates_valid_immutable_model_request() -> None:
    """Verify complete fields, identities, and read-only mappings are published."""
    target = _target()
    task = _task()
    access = _access()
    metadata: Extensions = {"traceLabel": "request-a"}
    extensions: Extensions = {"requestOption": [1, True, None]}
    builder = ModelRequestBuilder(target, task)
    returned = (
        builder.with_service_access(access)
        .with_metadata(metadata)
        .with_extensions(extensions)
    )
    request = builder.build()

    # Fluent identity, protocol conformance, and same-object nested fields prove
    # that Builder assembly adds no registry, normalization, or reconstruction.
    assert returned is builder
    assert isinstance(request, ModelRequest)
    assert validate_model_request(request) is request
    assert request.target is target
    assert request.task is task
    assert request.service_access is access
    assert request.metadata == metadata
    assert request.extensions == extensions
    _assert_raises(
        TypeError,
        lambda: _mutate_mapping(cast(dict[str, JsonValue], request.metadata)),
        "does not support item assignment",
    )
    _assert_raises(
        FrozenInstanceError,
        lambda: _mutate_request(request, _target()),
        "cannot assign to field",
    )


def test_builder_preserves_and_can_restore_missing_access() -> None:
    """Verify absent access is explicit and a fluent override can be cleared."""
    builder = ModelRequestBuilder(_target(), _task())
    absent = builder.build()
    access = _access()
    present = builder.with_service_access(access).build()
    cleared = builder.with_service_access(None).build()

    # None remains unresolved rather than synthesizing endpoint or anonymous
    # authorization. Clearing affects only the next immutable result.
    assert absent.service_access is None
    assert present.service_access is access
    assert cleared.service_access is None
    assert absent is not present
    assert present is not cleared


def test_builder_owns_channels_and_each_build_is_independent() -> None:
    """Verify caller changes and later fluent calls cannot alter prior outputs."""
    first_access = _access()
    second_access = _access("https://models.example.test/v2")
    metadata: dict[str, JsonValue] = {"attempt": 1}
    extensions: dict[str, JsonValue] = {"vendor.mode": "initial"}
    builder = (
        ModelRequestBuilder(_target(), _task())
        .with_service_access(first_access)
        .with_metadata(metadata)
        .with_extensions(extensions)
    )

    # Membership is captured by fluent calls before source mappings change.
    metadata["attempt"] = 99
    extensions["vendor.extra"] = False
    first = builder.build()

    # Replacing every optional channel affects only the second request. Fresh
    # read-only proxies keep both outputs independent from the mutable Builder.
    second = (
        builder.with_service_access(second_access)
        .with_metadata({"attempt": 2})
        .with_extensions({"vendor.mode": "later"})
        .build()
    )
    assert first.service_access is first_access
    assert second.service_access is second_access
    assert first.metadata == {"attempt": 1}
    assert first.extensions == {"vendor.mode": "initial"}
    assert second.metadata == {"attempt": 2}
    assert second.extensions == {"vendor.mode": "later"}
    assert first.metadata is not second.metadata
    assert first.extensions is not second.extensions


def test_builders_do_not_share_default_state() -> None:
    """Verify independent builders retain independent empty request channels."""
    first_builder = ModelRequestBuilder(_target(), _task())
    second_builder = ModelRequestBuilder(_target(), _task())
    first_builder.with_metadata({"owner": "first"}).with_extensions(
        {"vendor.owner": "first"}
    )

    # One construction flow cannot modify another's access or preservation data.
    first = first_builder.build()
    second = second_builder.build()
    assert first.metadata == {"owner": "first"}
    assert first.extensions == {"vendor.owner": "first"}
    assert second.service_access is None
    assert second.metadata == {}
    assert second.extensions == {}
    assert first.metadata is not second.metadata
    assert first.extensions is not second.extensions


def test_builder_delegates_complete_model_request_semantics() -> None:
    """Verify build propagates existing target and JSON Validator diagnostics."""
    invalid_target = ModelRequestBuilder(_target(service_id=""), _task())
    invalid_json = ModelRequestBuilder(_target(), _task()).with_metadata(
        {"invalid": cast(JsonValue, ("tuple",))}
    )

    # Both values satisfy fluent storage shape. Semantic failures arise only from
    # validate_model_request, proving the Builder owns no divergent rule copy.
    _assert_raises(
        ValueError,
        invalid_target.build,
        "OpenIdentifier must not be empty",
    )
    _assert_raises(TypeError, invalid_json.build, "JsonValue")


def test_builder_rejects_invalid_storage_without_partial_mutation() -> None:
    """Verify protocol and mapping checks fail before changing valid state."""
    target = _target()
    task = _task()
    access = _access()
    builder = ModelRequestBuilder(target, task).with_service_access(access)
    invalid_actions: tuple[tuple[Callable[[], object], str], ...] = (
        (
            lambda: ModelRequestBuilder(
                cast(ModelTarget, _IncompleteTarget(OpenIdentifier("service.only"))),
                task,
            ),
            "target must implement ModelTarget",
        ),
        (
            lambda: ModelRequestBuilder(
                target,
                cast(
                    ModelTaskRequest,
                    _IncompleteTask(
                        cast(
                            TaskDescriptor,
                            _Descriptor(OpenIdentifier("vendor.incomplete")),
                        )
                    ),
                ),
            ),
            "task must implement ModelTaskRequest",
        ),
        (
            lambda: builder.with_service_access(
                cast(ServiceAccess, _IncompleteAccess(None))
            ),
            "service_access must implement ServiceAccess or be None",
        ),
        (
            lambda: builder.with_metadata(cast(Extensions, [])),
            "metadata must be a mapping",
        ),
        (
            lambda: builder.with_extensions(cast(Extensions, {1: True})),
            "extensions keys must be strings",
        ),
    )

    # The original valid access survives every failure, and empty mappings prove
    # no partial replacement occurred before the exception was raised.
    for action, message in invalid_actions:
        _assert_raises(TypeError, action, message)
    built = builder.build()
    assert built.target is target
    assert built.task is task
    assert built.service_access is access
    assert built.metadata == {}
    assert built.extensions == {}


def test_builder_surface_and_private_output_boundary_are_exact() -> None:
    """Verify only envelope fields are public and concrete output stays private."""
    constructor_parameters = tuple(inspect.signature(ModelRequestBuilder).parameters)
    public_methods = {
        name
        for name, _ in inspect.getmembers(ModelRequestBuilder, inspect.isfunction)
        if not name.startswith("_")
    }

    # Required values and fluent methods map exactly to the ModelRequest protocol;
    # runtime and protocol-execution concerns cannot enter this domain Builder.
    assert constructor_parameters == ("target", "task")
    assert public_methods == {
        "build",
        "with_extensions",
        "with_metadata",
        "with_service_access",
    }
    for unrelated_name in (
        "interaction_mode",
        "options",
        "components",
        "protocol_payload",
        "authorization_handler",
        "transport",
    ):
        assert unrelated_name not in constructor_parameters
        assert unrelated_name not in public_methods

    # The protocol is the public result boundary; its immutable concrete storage
    # is internal and does not create another exported request model.
    assert not hasattr(builder_module, "__all__")
    assert "_BuiltModelRequest" not in mconet.core.domain.__all__
