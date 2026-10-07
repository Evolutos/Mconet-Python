"""Deterministic capability resolution from selected component metadata."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import cast

from mconet.core.domain import (
    Diagnostic,
    ErrorCategory,
    Extensions,
    InteractionPhase,
    JsonValue,
    ModelInteractionError,
    OpenIdentifier,
    validate_json_value_numbers,
)
from mconet.core.spi import (
    CapabilityRequirement,
    CapabilityResolution,
    ComponentSelectionResolution,
    InteractionCapability,
    SatisfiedCapability,
    SelectedComponent,
)

_UNSUPPORTED_FEATURE_CATEGORY = ErrorCategory(OpenIdentifier("unsupported_feature"))
_INVALID_COMPONENT_CONFIGURATION_CATEGORY = ErrorCategory(
    OpenIdentifier("invalid_component_configuration")
)
_CAPABILITY_RESOLUTION_PHASE = InteractionPhase(OpenIdentifier("capability_resolution"))
_UNSUPPORTED_CAPABILITY_CODE = "unsupported_capability"
_UNSUPPORTED_CAPABILITY_MESSAGE = "A required interaction capability is unsupported."
_AMBIGUOUS_PROVIDER_CODE = "ambiguous_capability_provider"
_AMBIGUOUS_PROVIDER_MESSAGE = (
    "Multiple selected components provide a capability at the same priority."
)
_OPTIONAL_UNSUPPORTED_CODE = "optional_capability_unsupported"
_OPTIONAL_UNSUPPORTED_MESSAGE = "An optional interaction capability is unsupported."
_SOURCE_PRIORITY = {"application": 0, "plugin": 1, "builtin": 2}
_EMPTY_FACTS: Extensions = MappingProxyType({})


@dataclass(frozen=True, slots=True)
class _DescriptorCapability:
    """Adapt one selected Descriptor capability ID to the public value protocol."""

    id: OpenIdentifier
    """Exact open capability identifier declared by the selected component."""

    version: str | None = None
    """No capability version is inferred from component implementation version."""

    attributes: Extensions = _EMPTY_FACTS
    """ID-only Descriptor declarations provide no constraint attributes."""

    extensions: Extensions = _EMPTY_FACTS
    """No unknown capability fields are invented during internal adaptation."""


def resolve_capabilities(
    requirements: tuple[CapabilityRequirement, ...],
    selected_components: ComponentSelectionResolution,
) -> CapabilityResolution:
    """Resolve required and optional capabilities from selected component metadata.

    The initial runtime profile consumes only capability IDs declared by the
    immutable descriptors in ``selected_components``. Application components
    outrank plugin components, which outrank built-ins. Distinct providers at
    the same highest source priority are ambiguous; absence is unsupported.

    Descriptor declarations have no attributes, so a non-empty constraints map
    cannot be proven satisfied. An unmatched required requirement fails with the
    stable unsupported-capability error. An unmatched optional requirement is
    retained in ``optional_unsupported`` and produces one stable warning at its
    declared source path. No component is invoked, no candidate outside the
    selected snapshot is observed, and no request or selection is modified.
    """
    requirements_value = cast(object, requirements)
    selected_value = cast(object, selected_components)

    # Immutable requirement order becomes satisfied-result order. Reject mutable
    # or unordered substitutes instead of silently copying or sorting them.
    if not isinstance(requirements_value, tuple):
        raise TypeError("requirements must be a tuple.")
    if not isinstance(selected_value, ComponentSelectionResolution):
        raise TypeError("selected_components must be a ComponentSelectionResolution.")

    validated_requirements: list[
        tuple[CapabilityRequirement, OpenIdentifier, bool, Extensions, str | None]
    ] = []
    for requirement in cast(tuple[object, ...], requirements_value):
        # Validate optional and required values alike before matching. A malformed
        # optional requirement must not become an apparently valid diagnostic.
        validated_requirements.append(_validate_requirement(requirement))

    satisfied: list[SatisfiedCapability] = []
    optional_unsupported: list[CapabilityRequirement] = []
    diagnostics: list[Diagnostic] = []
    for (
        requirement,
        capability_id,
        required,
        constraints,
        source_path,
    ) in validated_requirements:
        provider = _resolve_provider(
            capability_id,
            constraints,
            selected_components.components,
        )

        # Required absence is terminal, while optional absence remains an exact
        # resolution fact paired one-to-one with a non-sensitive warning.
        if provider is None:
            if required:
                raise _unsupported_capability_error()
            optional_unsupported.append(requirement)
            diagnostics.append(_optional_unsupported_diagnostic(source_path))
            continue

        capability = _DescriptorCapability(capability_id)

        # Use the fixed execution role as provenance rather than component name,
        # version, or a registry ID. The exact requirement object is retained.
        satisfied.append(
            SatisfiedCapability(
                requirement=requirement,
                capability=cast(InteractionCapability, capability),
                provider_id=provider.role.id.value,
            )
        )

    # Preserve collection order independently in all three immutable outputs.
    # The aggregate constructor revalidates result coherence before retention.
    return CapabilityResolution(
        satisfied=tuple(satisfied),
        optional_unsupported=tuple(optional_unsupported),
        diagnostics=tuple(diagnostics),
    )


def _validate_requirement(
    value: object,
) -> tuple[CapabilityRequirement, OpenIdentifier, bool, Extensions, str | None]:
    """Validate one open requirement and return its matching inputs."""
    if not isinstance(value, CapabilityRequirement):
        raise TypeError("requirements must contain CapabilityRequirement values.")

    capability_id = cast(object, value.capability_id)
    required = cast(object, value.required)
    constraints = cast(object, value.constraints)
    source_path = cast(object, value.source_path)
    extensions = cast(object, value.extensions)

    # Runtime-checkable protocols verify property presence only. Validate every
    # returned value so dynamic implementations cannot alter matching semantics.
    if not isinstance(capability_id, OpenIdentifier):
        raise TypeError("requirement capability_id must be an OpenIdentifier.")
    if type(required) is not bool:
        raise TypeError("requirement required must be a boolean.")
    typed_constraints = _validate_portable_mapping(constraints, "constraints")
    if source_path is not None and not isinstance(source_path, str):
        raise TypeError("requirement source_path must be a string or None.")
    _validate_portable_mapping(extensions, "extensions")

    return value, capability_id, required, typed_constraints, source_path


def _validate_portable_mapping(value: object, field_name: str) -> Extensions:
    """Require a string-keyed mapping containing portable JSON values."""
    if not isinstance(value, Mapping):
        raise TypeError(f"requirement {field_name} must be a mapping.")

    source = cast(Mapping[object, object], value)
    if any(not isinstance(key, str) for key in source):
        raise TypeError(f"requirement {field_name} keys must be strings.")

    # Validate each recursive value for shape, cycles, finite numbers, and safe
    # integers without copying or interpreting constraint/extension semantics.
    typed_source = cast(Mapping[str, JsonValue], source)
    for item in typed_source.values():
        validate_json_value_numbers(item)
    return typed_source


def _resolve_provider(
    capability_id: OpenIdentifier,
    constraints: Extensions,
    selected_components: tuple[SelectedComponent, ...],
) -> SelectedComponent | None:
    """Return the unique highest-priority provider, or None when unsupported."""
    # Descriptor declarations expose IDs only. Non-empty constraints cannot be
    # evaluated or proven by this release profile, so they behave as no match
    # instead of becoming an implicit expression language or being ignored.
    if constraints:
        return None

    matching = tuple(
        selected
        for selected in selected_components
        if capability_id in selected.descriptor.capabilities
    )
    if not matching:
        return None

    # Apply the documented direct/plugin/builtin source precedence before
    # ambiguity. Lower-priority declarations cannot create or resolve a tie.
    highest_priority = min(
        _SOURCE_PRIORITY[selected.descriptor.source] for selected in matching
    )
    highest = tuple(
        selected
        for selected in matching
        if _SOURCE_PRIORITY[selected.descriptor.source] == highest_priority
    )

    # The same stateless component may occupy several execution roles and still
    # represents one provider. Group by exact instance identity, never descriptor
    # equality or diagnostic name, which need not be globally unique.
    providers_by_identity: dict[int, list[SelectedComponent]] = {}
    for selected in highest:
        providers_by_identity.setdefault(id(selected.component), []).append(selected)

    if len(providers_by_identity) != 1:
        raise _ambiguous_capability_provider_error()

    provider_roles = next(iter(providers_by_identity.values()))
    # Choose only a stable provenance label for one already-unique provider.
    # Lexical role order does not select between component instances.
    return min(provider_roles, key=lambda item: item.role.id.value)


def _unsupported_capability_error() -> ModelInteractionError:
    """Create the stable failure for one unmatched required capability."""
    # Fixed text excludes open capability IDs, constraints, source paths, roles,
    # and descriptor metadata so application-controlled values do not enter logs.
    return ModelInteractionError(
        category=_UNSUPPORTED_FEATURE_CATEGORY,
        phase=_CAPABILITY_RESOLUTION_PHASE,
        code=_UNSUPPORTED_CAPABILITY_CODE,
        message=_UNSUPPORTED_CAPABILITY_MESSAGE,
    )


def _ambiguous_capability_provider_error() -> ModelInteractionError:
    """Create the stable failure for same-priority capability providers."""
    # The message reports only the invariant and never candidate count, order,
    # component names, versions, roles, or the requested open capability ID.
    return ModelInteractionError(
        category=_INVALID_COMPONENT_CONFIGURATION_CATEGORY,
        phase=_CAPABILITY_RESOLUTION_PHASE,
        code=_AMBIGUOUS_PROVIDER_CODE,
        message=_AMBIGUOUS_PROVIDER_MESSAGE,
    )


def _optional_unsupported_diagnostic(source_path: str | None) -> Diagnostic:
    """Create one stable warning for an unmatched optional capability."""
    # Capability IDs, constraints, component metadata, and candidate counts stay
    # out of text/details. The explicit requirement source path is retained only
    # in Diagnostic.path, whose contract exists for this provenance purpose.
    return Diagnostic(
        code=_OPTIONAL_UNSUPPORTED_CODE,
        severity="warning",
        phase=_CAPABILITY_RESOLUTION_PHASE,
        message=_OPTIONAL_UNSUPPORTED_MESSAGE,
        path=source_path,
    )
