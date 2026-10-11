"""Internal immutable component bindings used by integration resolution."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Protocol, cast, runtime_checkable

from mconet.core.domain import (
    InteractionMode,
    ModelTarget,
    ServiceAccess,
    TaskDescriptor,
)
from mconet.core.spi import (
    ComponentDescriptor,
    ModelIntegrationMatch,
    ModelTargetMatch,
    RuntimeComponent,
    TaskMatch,
)

_EMPTY_EXTENSIONS: Mapping[str, object] = MappingProxyType({})


def _empty_extensions() -> Mapping[str, object]:
    """Return the shared immutable empty internal-extension mapping."""
    # Empty membership has no caller-owned bindings, so internal SDK-created
    # bindings can safely share one allocation without mutable coupling.
    return _EMPTY_EXTENSIONS


@runtime_checkable
class _ModelTargetMatcher(Protocol):
    """Internal behavior required to evaluate one model target."""

    def match(self, target: ModelTarget) -> ModelTargetMatch | None:
        """Return target match facts, or None when this binding is inapplicable."""
        # Implementations remain SDK/plugin-owned objects; the binding stores the
        # exact matcher rather than a registry ID or a name-based lookup key.
        ...


@runtime_checkable
class _TaskMatcher(Protocol):
    """Internal behavior required to evaluate one task and interaction mode."""

    def match(
        self,
        task: TaskDescriptor,
        mode: InteractionMode,
    ) -> TaskMatch | None:
        """Return task-and-mode facts, or None when this binding is inapplicable."""
        # Keeping both inputs in one matcher preserves the current TaskMatch
        # contract without creating an independent mode matcher or registry.
        ...


@dataclass(frozen=True, slots=True)
class ModelIntegrationBinding:
    """Bind matchers to an explicit immutable set of component instances.

    This type is internal to resolver assembly and is intentionally absent from
    public package exports. Every component role stores concrete instances rather
    than component IDs, registry keys, factories, or mutable registration state.
    Role-specific behavior protocols are checked by later consumers as those
    contracts are introduced; this boundary requires the shared descriptor now.
    """

    id: str
    """Stable SDK/plugin-owned binding label used only for plan diagnostics."""

    version: str
    """Binding implementation version preserved for the resolved plan snapshot."""

    target_matcher: _ModelTargetMatcher
    """Concrete matcher used to evaluate the request's ModelTarget."""

    task_matcher: _TaskMatcher
    """Concrete matcher used to evaluate TaskDescriptor and InteractionMode."""

    task_protocol_adapter: RuntimeComponent
    """Single protocol adapter instance explicitly owned by this binding."""

    authorization_handlers: tuple[RuntimeComponent, ...]
    """Ordered authorization handler candidates scoped to this binding."""

    default_service_access: ServiceAccess | None
    """Optional non-sensitive access defaults explicitly owned by the binding."""

    payload_encoders: tuple[RuntimeComponent, ...]
    """Ordered payload encoder candidates explicitly available to this binding."""

    payload_decoders: tuple[RuntimeComponent, ...]
    """Ordered success/error decoder candidates available to this binding."""

    transports: tuple[RuntimeComponent, ...]
    """Ordered transport candidates explicitly available to this binding."""

    extensions: Mapping[str, object] = field(default_factory=_empty_extensions)
    """Read-only top-level snapshot of SDK/plugin-owned internal extension values."""

    def __post_init__(self) -> None:
        """Validate the complete explicit binding and freeze extension membership."""
        binding_id = cast(object, self.id)
        version = cast(object, self.version)
        target_matcher = cast(object, self.target_matcher)
        task_matcher = cast(object, self.task_matcher)
        default_service_access = cast(object, self.default_service_access)

        # Binding identity is diagnostic metadata, not a component selection key;
        # retain text exactly while rejecting non-string dynamic values.
        if not isinstance(binding_id, str):
            raise TypeError("ModelIntegrationBinding id must be a string.")
        if not isinstance(version, str):
            raise TypeError("ModelIntegrationBinding version must be a string.")

        # Structural matcher boundaries permit private SDK and plugin classes
        # without inheritance or registration in a writable global registry.
        if not isinstance(target_matcher, _ModelTargetMatcher):
            raise TypeError(
                "ModelIntegrationBinding target_matcher must implement match."
            )
        if not isinstance(task_matcher, _TaskMatcher):
            raise TypeError(
                "ModelIntegrationBinding task_matcher must implement match."
            )

        # The adapter is a required single instance. Its descriptor proves the
        # common component metadata boundary before its behavior protocol exists.
        _validate_component(self.task_protocol_adapter, "task_protocol_adapter")

        # Candidate roles use immutable ordered tuples. Validate each independently
        # so missing metadata is attributed to its exact binding field.
        _validate_components(self.authorization_handlers, "authorization_handlers")
        _validate_components(self.payload_encoders, "payload_encoders")
        _validate_components(self.payload_decoders, "payload_decoders")
        _validate_components(self.transports, "transports")

        # Access defaults are optional but must expose the complete structural
        # ServiceAccess surface when supplied; resolution and validation occur later.
        if default_service_access is not None and not isinstance(
            default_service_access, ServiceAccess
        ):
            raise TypeError(
                "ModelIntegrationBinding default_service_access must implement "
                "ServiceAccess or be None."
            )

        # Detach top-level internal extension membership from SDK/plugin assembly
        # dictionaries before the binding can be shared across client interactions.
        object.__setattr__(self, "extensions", _snapshot_extensions(self.extensions))


def match_binding(
    binding: ModelIntegrationBinding,
    target: ModelTarget,
    task: TaskDescriptor,
    mode: InteractionMode,
) -> ModelIntegrationMatch | None:
    """Return the combined match facts when a binding applies to a request.

    The target matcher runs first; the task matcher runs only after the target
    matched, so evaluation order is fixed and a rejected target never consults
    the task matcher. ``None`` and a result with ``matched=False`` both mean
    the binding does not apply.

    Args:
        binding: Binding whose two matchers are evaluated.
        target: Model target being resolved.
        task: Task descriptor being resolved.
        mode: Interaction mode being resolved.

    Returns:
        Both successful results, or ``None`` when either matcher rejects.

    Raises:
        TypeError: If a matcher returns a value other than its match type or
            ``None``.
    """
    target_match = cast(object, binding.target_matcher.match(target))
    if target_match is None:
        return None
    if not isinstance(target_match, ModelTargetMatch):
        raise TypeError(
            "ModelIntegrationBinding target_matcher must return ModelTargetMatch "
            "or None."
        )
    if not target_match.matched:
        return None

    task_match = cast(object, binding.task_matcher.match(task, mode))
    if task_match is None:
        return None
    if not isinstance(task_match, TaskMatch):
        raise TypeError(
            "ModelIntegrationBinding task_matcher must return TaskMatch or None."
        )
    if not task_match.matched:
        return None
    return ModelIntegrationMatch(target_match, task_match)


def _validate_component(value: object, field_name: str) -> None:
    """Require one concrete runtime component with nominal descriptor metadata."""
    # Structural RuntimeComponent recognition allows any behavior implementation
    # while excluding arbitrary objects with no static component metadata.
    if not isinstance(value, RuntimeComponent):
        raise TypeError(
            f"ModelIntegrationBinding {field_name} must implement RuntimeComponent."
        )

    # Validate the descriptor itself nominally because runtime-checkable Protocol
    # recognition only proves that a descriptor attribute exists.
    descriptor = cast(object, value.descriptor)
    if not isinstance(descriptor, ComponentDescriptor):
        raise TypeError(
            f"ModelIntegrationBinding {field_name} descriptor must be a "
            "ComponentDescriptor."
        )


def _validate_components(value: object, field_name: str) -> None:
    """Require an immutable ordered tuple of concrete runtime components."""
    # A tuple prevents plugins or application code from changing candidate
    # membership or priority order after the internal binding is assembled.
    if not isinstance(value, tuple):
        raise TypeError(f"ModelIntegrationBinding {field_name} must be a tuple.")
    for component in cast(tuple[object, ...], value):
        _validate_component(component, field_name)


def _snapshot_extensions(value: object) -> Mapping[str, object]:
    """Copy string-keyed internal extensions into read-only top-level storage."""
    # Internal values may be local runtime objects, but deterministic lookup still
    # requires a mapping with explicit string member names.
    if not isinstance(value, Mapping):
        raise TypeError("ModelIntegrationBinding extensions must be a mapping.")
    source = cast(Mapping[object, object], value)
    if any(not isinstance(key, str) for key in source):
        raise TypeError("ModelIntegrationBinding extensions keys must be strings.")

    # Reuse the immutable empty singleton or snapshot non-empty membership while
    # preserving opaque nested values by identity for their owning integration.
    if not source:
        return _EMPTY_EXTENSIONS
    snapshot = dict(cast(Mapping[str, object], source))
    return MappingProxyType(snapshot)
