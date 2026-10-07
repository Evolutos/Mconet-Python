"""Immutable component snapshots produced by model integration resolution."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal, cast

from mconet.core.domain import ServiceAccess
from mconet.core.spi.component_descriptor import ComponentDescriptor
from mconet.core.spi.model_integration_match import ModelIntegrationMatch
from mconet.core.spi.runtime_component import RuntimeComponent

_EMPTY_EXTENSIONS: Mapping[str, object] = MappingProxyType({})


def _empty_extensions() -> Mapping[str, object]:
    """Return the shared immutable empty plan-extension mapping."""
    # An empty mapping contains no caller-owned membership, so plans may share
    # this allocation without coupling otherwise independent interactions.
    return _EMPTY_EXTENSIONS


@dataclass(frozen=True, slots=True)
class ModelIntegrationPlan:
    """Store the fixed integration inputs selected for one interaction.

    A direct plan contains only the explicitly injected protocol adapter. A
    resolved plan snapshots binding provenance, match facts, access defaults,
    and the current concrete component candidates. The plan stores instances,
    not component IDs or a reference to the internal binding, so subsequent
    execution never performs registry lookup or observes binding replacement.

    Only component roles with implemented contracts are represented here.
    Streaming, artifact, operation, and capability roles are added when their
    corresponding behavior contracts become executable SDK features.
    """

    source: Literal["direct_adapter", "resolved_binding"]
    """Closed provenance distinguishing direct injection from resolver output."""

    binding_id: str | None
    """Resolved binding diagnostic label, absent for a direct adapter plan."""

    binding_version: str | None
    """Resolved binding version snapshot, absent for a direct adapter plan."""

    match: ModelIntegrationMatch | None
    """Completed resolver match facts, absent for a direct adapter plan."""

    task_protocol_adapter: RuntimeComponent
    """Exact protocol adapter instance fixed for the interaction."""

    authorization_handlers: tuple[RuntimeComponent, ...] = ()
    """Ordered binding-owned authorization handler candidates."""

    default_service_access: ServiceAccess | None = None
    """Optional binding-owned access defaults used by later access resolution."""

    payload_encoders: tuple[RuntimeComponent, ...] = ()
    """Ordered binding-owned payload encoder candidates."""

    payload_decoders: tuple[RuntimeComponent, ...] = ()
    """Ordered binding-owned success and error decoder candidates."""

    transports: tuple[RuntimeComponent, ...] = ()
    """Ordered binding-owned transport candidates."""

    extensions: Mapping[str, object] = field(default_factory=_empty_extensions)
    """Read-only top-level snapshot of plan-specific extension values."""

    def __post_init__(self) -> None:
        """Validate plan provenance, match completion, and snapshot boundaries."""
        source = cast(object, self.source)
        binding_id = cast(object, self.binding_id)
        binding_version = cast(object, self.binding_version)
        match = cast(object, self.match)
        default_service_access = cast(object, self.default_service_access)

        # Source is a closed control-flow fact. Validate its primitive type
        # separately so dynamic callers receive a precise boundary failure.
        if not isinstance(source, str):
            raise TypeError("ModelIntegrationPlan source must be a string.")
        if source not in ("direct_adapter", "resolved_binding"):
            raise ValueError(
                "ModelIntegrationPlan source must be direct_adapter or "
                "resolved_binding."
            )

        # Every plan fixes one concrete adapter. The common runtime protocol and
        # nominal descriptor are checked before either provenance branch is used.
        _validate_component(self.task_protocol_adapter, "task_protocol_adapter")

        # Candidate tuples preserve binding declaration order and instance
        # identity while preventing membership changes after resolution. Check
        # their shapes before provenance semantics so invalid dynamic containers
        # cannot trigger arbitrary truth-value behavior in the direct branch.
        _validate_components(self.authorization_handlers, "authorization_handlers")
        _validate_components(self.payload_encoders, "payload_encoders")
        _validate_components(self.payload_decoders, "payload_decoders")
        _validate_components(self.transports, "transports")

        # Access defaults remain unresolved at this stage, but a supplied object
        # must already expose the complete structural ServiceAccess contract.
        if default_service_access is not None and not isinstance(
            default_service_access, ServiceAccess
        ):
            raise TypeError(
                "ModelIntegrationPlan default_service_access must implement "
                "ServiceAccess or be None."
            )

        # A direct adapter bypasses binding resolution and therefore cannot carry
        # binding metadata, match facts, defaults, or binding-owned candidates.
        if source == "direct_adapter":
            if binding_id is not None:
                raise ValueError(
                    "ModelIntegrationPlan direct_adapter binding_id must be None."
                )
            if binding_version is not None:
                raise ValueError(
                    "ModelIntegrationPlan direct_adapter binding_version must be None."
                )
            if match is not None:
                raise ValueError(
                    "ModelIntegrationPlan direct_adapter match must be None."
                )
            _validate_direct_binding_values(self)
        else:
            # Resolver output must preserve complete binding provenance and the
            # exact successful target and task/mode decisions that selected it.
            if not isinstance(binding_id, str):
                raise TypeError(
                    "ModelIntegrationPlan resolved_binding binding_id must be a string."
                )
            if not isinstance(binding_version, str):
                raise TypeError(
                    "ModelIntegrationPlan resolved_binding binding_version must be "
                    "a string."
                )
            if not isinstance(match, ModelIntegrationMatch):
                raise TypeError(
                    "ModelIntegrationPlan resolved_binding match must be a "
                    "ModelIntegrationMatch."
                )
            if not match.target.matched or not match.task.matched:
                raise ValueError(
                    "ModelIntegrationPlan resolved_binding match must contain "
                    "successful target and task results."
                )

        # Copy extension membership after all semantic validation so a failed
        # plan never partially installs caller-owned mutable state.
        object.__setattr__(self, "extensions", _snapshot_extensions(self.extensions))


def _validate_direct_binding_values(plan: ModelIntegrationPlan) -> None:
    """Require a direct plan to contain no values sourced from a binding."""
    # The direct path intentionally fixes only its adapter. Allowing binding
    # candidates here would blur precedence and could make the bypass path depend
    # on a resolver result that was never produced.
    if plan.authorization_handlers:
        raise ValueError(
            "ModelIntegrationPlan direct_adapter authorization_handlers must be empty."
        )
    if plan.default_service_access is not None:
        raise ValueError(
            "ModelIntegrationPlan direct_adapter default_service_access must be None."
        )
    if plan.payload_encoders:
        raise ValueError(
            "ModelIntegrationPlan direct_adapter payload_encoders must be empty."
        )
    if plan.payload_decoders:
        raise ValueError(
            "ModelIntegrationPlan direct_adapter payload_decoders must be empty."
        )
    if plan.transports:
        raise ValueError(
            "ModelIntegrationPlan direct_adapter transports must be empty."
        )


def _validate_component(value: object, field_name: str) -> None:
    """Require one concrete runtime component with nominal descriptor metadata."""
    # Structural conformance admits SDK, plugin, and application implementations
    # without inheritance while excluding objects with no component metadata.
    if not isinstance(value, RuntimeComponent):
        raise TypeError(
            f"ModelIntegrationPlan {field_name} must implement RuntimeComponent."
        )

    # A runtime-checkable protocol proves only attribute presence. Requiring the
    # nominal value prevents malformed descriptor payloads from reaching selection.
    descriptor = cast(object, value.descriptor)
    if not isinstance(descriptor, ComponentDescriptor):
        raise TypeError(
            f"ModelIntegrationPlan {field_name} descriptor must be a "
            "ComponentDescriptor."
        )


def _validate_components(value: object, field_name: str) -> None:
    """Require an immutable ordered tuple of concrete runtime components."""
    # Lists are rejected even when currently equal because later mutation would
    # change candidate membership or precedence after integration resolution.
    if not isinstance(value, tuple):
        raise TypeError(f"ModelIntegrationPlan {field_name} must be a tuple.")
    for component in cast(tuple[object, ...], value):
        _validate_component(component, field_name)


def _snapshot_extensions(value: object) -> Mapping[str, object]:
    """Copy string-keyed plan extensions into read-only top-level storage."""
    # Extension names are stable lookup keys. Values remain opaque local objects
    # and are deliberately not serialized, copied deeply, or interpreted here.
    if not isinstance(value, Mapping):
        raise TypeError("ModelIntegrationPlan extensions must be a mapping.")
    source = cast(Mapping[object, object], value)
    if any(not isinstance(key, str) for key in source):
        raise TypeError("ModelIntegrationPlan extensions keys must be strings.")

    # Reuse the empty immutable value or detach non-empty membership from the
    # caller while preserving nested opaque values by identity.
    if not source:
        return _EMPTY_EXTENSIONS
    snapshot = dict(cast(Mapping[str, object], source))
    return MappingProxyType(snapshot)
