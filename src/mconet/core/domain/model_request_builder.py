"""Fluent construction for validated immutable model interaction requests."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Self, cast

from mconet.core.domain.extensions import Extensions
from mconet.core.domain.json_value import JsonValue
from mconet.core.domain.model_request import ModelRequest
from mconet.core.domain.model_request_validation import validate_model_request
from mconet.core.domain.model_target import ModelTarget
from mconet.core.domain.model_task_request import ModelTaskRequest
from mconet.core.domain.service_access import ServiceAccess


@dataclass(frozen=True, slots=True)
class _BuiltModelRequest:
    """Store one immutable task-neutral request produced by the builder."""

    target: ModelTarget
    """Exact caller-supplied model interaction target."""

    task: ModelTaskRequest
    """Exact caller-supplied open task request."""

    service_access: ServiceAccess | None
    """Optional exact request-level unresolved service access override."""

    metadata: Extensions
    """Read-only request metadata membership snapshot."""

    extensions: Extensions
    """Read-only unknown-field membership snapshot."""


class ModelRequestBuilder:
    """Accumulate fields for one validated task-neutral model request.

    Target and task are required and remain separate identity-preserved values.
    Request-level service access is optional and never synthesized from either
    value. Metadata and extensions are independently snapshotted. Each
    :meth:`build` call creates a fresh private immutable implementation of the
    open :class:`ModelRequest` protocol and delegates complete target, task,
    access, and JSON semantics to :func:`validate_model_request`.

    The builder owns no interaction mode, runtime options, components, protocol
    payload, authorization resolution, or transport behavior. It is mutable and
    intentionally not thread-safe; callers should share only completed requests.
    """

    __slots__ = (
        "_extensions",
        "_metadata",
        "_service_access",
        "_target",
        "_task",
    )

    def __init__(self, target: ModelTarget, task: ModelTaskRequest) -> None:
        """Start a builder with both required envelope values.

        Args:
            target: Structural routing target retained by identity.
            task: Structural task request retained by identity.

        Raises:
            TypeError: If either value does not implement its open protocol.
        """
        candidate_target = cast(object, target)
        candidate_task = cast(object, task)
        # Structural checks protect the builder's readable storage boundary while
        # leaving all nested and semantic rules to the composed Validator.
        if not isinstance(candidate_target, ModelTarget):
            raise TypeError("ModelRequestBuilder target must implement ModelTarget.")
        if not isinstance(candidate_task, ModelTaskRequest):
            raise TypeError("ModelRequestBuilder task must implement ModelTaskRequest.")

        # Required immutable values retain exact identity. Optional state starts
        # absent or in fresh containers owned by this construction flow alone.
        self._target = candidate_target
        self._task = candidate_task
        self._service_access: ServiceAccess | None = None
        self._metadata: dict[str, JsonValue] = {}
        self._extensions: dict[str, JsonValue] = {}

    def with_service_access(self, service_access: ServiceAccess | None) -> Self:
        """Replace or clear the request-level service access override.

        Args:
            service_access: Structural unresolved access input, or ``None`` to
                leave resolution to later interaction or client layers.

        Returns:
            This builder for fluent construction.

        Raises:
            TypeError: If a present value does not implement ``ServiceAccess``.
        """
        candidate = cast(object, service_access)
        # None remains a meaningful unresolved state. A present value must expose
        # the complete open access surface before replacing valid builder state.
        if candidate is not None and not isinstance(candidate, ServiceAccess):
            raise TypeError(
                "ModelRequestBuilder service_access must implement "
                "ServiceAccess or be None."
            )
        self._service_access = service_access
        return self

    def with_metadata(self, metadata: Extensions) -> Self:
        """Replace request metadata with an owned membership snapshot.

        Args:
            metadata: String-keyed descriptive JSON values.

        Returns:
            This builder for fluent construction.

        Raises:
            TypeError: If ``metadata`` is not a string-keyed mapping.
        """
        # Capture membership immediately so caller changes cannot alter a later
        # request built from the current fluent state.
        self._metadata = _snapshot_mapping(metadata, "metadata")
        return self

    def with_extensions(self, extensions: Extensions) -> Self:
        """Replace unknown request fields with an owned membership snapshot.

        Args:
            extensions: String-keyed forward-compatible JSON values.

        Returns:
            This builder for fluent construction.

        Raises:
            TypeError: If ``extensions`` is not a string-keyed mapping.
        """
        # Unknown fields stay independent from descriptive metadata and cannot
        # become routing, task, access, option, component, or transport values.
        self._extensions = _snapshot_mapping(extensions, "extensions")
        return self

    def build(self) -> ModelRequest:
        """Create and validate a fresh immutable model request.

        Returns:
            A private immutable implementation of the public ``ModelRequest``
            protocol containing the builder's current values.

        Raises:
            TypeError: If a stored field or nested value has an invalid shape.
            ValueError: If target, task, access, or JSON semantics are invalid.
            ModelInteractionError: If a known task exceeds its supported scope.
        """
        # Freeze both mappings into fresh read-only snapshots for this result.
        # Later builder replacements and dynamic caller writes cannot mutate an
        # already published ModelRequest.
        request: ModelRequest = _BuiltModelRequest(
            target=self._target,
            task=self._task,
            service_access=self._service_access,
            metadata=_freeze_mapping(self._metadata),
            extensions=_freeze_mapping(self._extensions),
        )
        # The existing Validator remains the only semantic authority and returns
        # this exact private value without rebuilding or changing field ownership.
        return validate_model_request(request)


def _snapshot_mapping(value: Extensions, field_name: str) -> dict[str, JsonValue]:
    """Return owned string-keyed membership without interpreting JSON values."""
    candidate = cast(object, value)
    # Mapping permits custom read-only sources, while portable JSON object
    # membership still requires every top-level key to be a string.
    if not isinstance(candidate, Mapping):
        raise TypeError(f"ModelRequestBuilder {field_name} must be a mapping.")
    source = cast(Mapping[object, object], candidate)
    if any(not isinstance(key, str) for key in source):
        raise TypeError(f"ModelRequestBuilder {field_name} keys must be strings.")

    # Recursive JSON validation is deferred to build(), preventing a second copy
    # of cycle, finite-number, safe-integer, and portable shape rules.
    return dict(cast(Mapping[str, JsonValue], source))


def _freeze_mapping(value: Mapping[str, JsonValue]) -> Extensions:
    """Copy builder-owned membership into a read-only request snapshot."""
    # A fresh dictionary separates this build from both current builder storage
    # and other results; MappingProxyType prevents mutation through the output.
    return MappingProxyType(dict(value))
