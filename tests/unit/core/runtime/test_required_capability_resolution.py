"""Tests for required capability resolution from selected components."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal, cast

from mconet.core.domain import Extensions, ModelInteractionError, OpenIdentifier
from mconet.core.runtime._required_capability_resolution import (
    resolve_required_capabilities,
)
from mconet.core.spi import (
    CapabilityRequirement,
    ComponentDescriptor,
    ComponentRole,
    ComponentSelectionResolution,
    SelectedComponent,
)


def _empty_extensions() -> Extensions:
    """Return independent empty mapping storage for requirement fixtures."""
    # Separate dictionaries make identity-sensitive tests independent without
    # affecting the read-only Extensions contract observed by production code.
    return {}


@dataclass(frozen=True, slots=True)
class _Requirement:
    """Complete open requirement fixture for deterministic resolver tests."""

    capability_id: OpenIdentifier
    """Exact open capability identity requested by the interaction."""

    required: bool
    """Whether a missing match must terminate resolution."""

    constraints: Extensions = field(default_factory=_empty_extensions)
    """Portable facts that ID-only Descriptor declarations cannot prove."""

    source_path: str | None = None
    """Optional diagnostic origin retained by successful result identity."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Unknown requirement facts preserved without affecting identity matching."""


@dataclass(frozen=True, slots=True)
class _Component:
    """Selected runtime component fixture exposing immutable Descriptor metadata."""

    descriptor: ComponentDescriptor
    """Capability IDs and provenance consumed without invoking behavior."""


@dataclass(frozen=True, slots=True)
class _IncompleteRequirement:
    """Requirement-like fixture missing the complete structural surface."""

    capability_id: OpenIdentifier
    """Identity alone is insufficient for deterministic capability resolution."""


@dataclass(frozen=True, slots=True)
class _MalformedRequirement:
    """Structurally complete requirement returning dynamic malformed values."""

    capability_id: object
    required: object
    constraints: object
    source_path: object
    extensions: object


def _requirement(
    capability_id: str,
    *,
    required: bool = True,
    constraints: Extensions | None = None,
) -> _Requirement:
    """Build one distinguishable complete requirement."""
    # Explicit source and extension facts prove a successful result retains the
    # exact requirement object rather than reconstructing a reduced copy.
    return _Requirement(
        capability_id=OpenIdentifier(capability_id),
        required=required,
        constraints={} if constraints is None else constraints,
        source_path=f"task.capabilities.{capability_id}",
        extensions={"fixture": True},
    )


def _selected(
    role_id: str,
    source: Literal["builtin", "plugin", "application"],
    *capability_ids: str,
    component: _Component | None = None,
) -> SelectedComponent:
    """Build one selected component declaring open capability identifiers."""
    # Reusing an explicit component exercises identity deduplication across roles;
    # otherwise each fixture represents a distinct provider instance.
    selected_component = component
    if selected_component is None:
        descriptor = ComponentDescriptor(
            name=f"component:{role_id}",
            version="1",
            source=source,
            capabilities=frozenset(
                OpenIdentifier(capability_id) for capability_id in capability_ids
            ),
        )
        selected_component = _Component(descriptor)
    return SelectedComponent(
        ComponentRole(OpenIdentifier(role_id)),
        selected_component,
        selected_component.descriptor,
    )


def _resolution(*components: SelectedComponent) -> ComponentSelectionResolution:
    """Build an immutable selected-component snapshot in resolver order."""
    # The value constructor verifies members and role uniqueness before required
    # capability resolution observes Descriptor metadata.
    return ComponentSelectionResolution(components)


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> BaseException:
    """Require one action to fail through the intended stable branch."""
    try:
        action()
    except exception_type as error:
        # Stable fragments prevent incidental fixture or protocol failures from
        # making negative resolver tests appear successful.
        assert message in str(error)
        return error
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_empty_requirements_produce_complete_empty_resolution() -> None:
    """Resolve an empty required set without inventing capability facts."""
    result = resolve_required_capabilities((), _resolution())

    assert result.satisfied == ()
    assert result.optional_unsupported == ()
    assert result.diagnostics == ()


def test_resolves_required_id_from_exact_selected_component() -> None:
    """Bind one required ID to the matching selected Descriptor declaration."""
    requirement = _requirement("model.text.output")
    provider = _selected(
        "codec.response.success-decoder",
        "plugin",
        "model.text.output",
    )

    result = resolve_required_capabilities((requirement,), _resolution(provider))

    assert len(result.satisfied) == 1
    satisfied = result.satisfied[0]
    assert satisfied.requirement is requirement
    assert satisfied.capability.id is requirement.capability_id
    assert satisfied.capability.version is None
    assert satisfied.capability.attributes == {}
    assert satisfied.capability.extensions == {}
    assert satisfied.provider_id == "codec.response.success-decoder"
    assert result.optional_unsupported == ()
    assert result.diagnostics == ()


def test_preserves_required_requirement_order_and_distinct_identity() -> None:
    """Return satisfactions in collection order without semantic deduplication."""
    text = _requirement("model.text.output")
    tools = _requirement("model.tool.calling")
    duplicate_text = _requirement("model.text.output")
    provider = _selected(
        "protocol.adapter",
        "plugin",
        "model.text.output",
        "model.tool.calling",
    )

    result = resolve_required_capabilities(
        (text, tools, duplicate_text),
        _resolution(provider),
    )

    # Each collected requirement is an independent fact even when open IDs are
    # equal; result order follows collection rather than identifier sorting.
    assert tuple(item.requirement for item in result.satisfied) == (
        text,
        tools,
        duplicate_text,
    )
    assert all(item.provider_id == "protocol.adapter" for item in result.satisfied)


def test_ignores_optional_requirements_until_policy_step() -> None:
    """Validate but defer optional requirements without diagnostics or failure."""
    optional = _requirement("vendor.response.citations", required=False)

    result = resolve_required_capabilities((optional,), _resolution())

    # The next atomic step owns optional unsupported membership and diagnostics;
    # this required-only step leaves both outputs explicitly empty.
    assert result == result.__class__()
    assert result.satisfied == ()


def test_source_priority_prefers_application_then_plugin_then_builtin() -> None:
    """Choose one highest-source provider before evaluating ambiguity."""
    requirement = _requirement("transport.unary")
    builtin = _selected("transport.builtin", "builtin", "transport.unary")
    plugin = _selected("transport.plugin", "plugin", "transport.unary")
    application = _selected(
        "transport.application",
        "application",
        "transport.unary",
    )

    plugin_result = resolve_required_capabilities(
        (requirement,),
        _resolution(builtin, plugin),
    )
    application_result = resolve_required_capabilities(
        (requirement,),
        _resolution(builtin, plugin, application),
    )

    # Tuple order does not grant priority: explicit provenance always wins.
    assert plugin_result.satisfied[0].provider_id == "transport.plugin"
    assert application_result.satisfied[0].provider_id == "transport.application"


def test_same_priority_distinct_providers_are_ambiguous() -> None:
    """Reject two different highest-priority components for one required ID."""
    requirement = _requirement("codec.json")
    first = _selected("codec.encoder", "plugin", "codec.json")
    second = _selected("codec.decoder", "plugin", "codec.json")

    raised = cast(
        ModelInteractionError,
        _assert_raises(
            ModelInteractionError,
            lambda: resolve_required_capabilities(
                (requirement,),
                _resolution(first, second),
            ),
            "Multiple selected components provide a required capability",
        ),
    )

    assert str(raised.category) == "invalid_component_configuration"
    assert str(raised.phase) == "capability_resolution"
    assert raised.code == "ambiguous_capability_provider"
    assert raised.status_code is None
    assert raised.service_error_code is None
    assert raised.request_id is None
    assert raised.recovery is None
    assert raised.cause is None
    assert "codec.json" not in str(raised)
    assert "encoder" not in str(raised)


def test_shared_component_across_roles_is_one_provider() -> None:
    """Deduplicate one provider instance selected for multiple execution roles."""
    descriptor = ComponentDescriptor(
        "shared-codec",
        "1",
        "application",
        capabilities=frozenset((OpenIdentifier("codec.json"),)),
    )
    shared = _Component(descriptor)
    success = _selected(
        "codec.response.success-decoder",
        "application",
        component=shared,
    )
    error = _selected(
        "codec.response.error-decoder",
        "application",
        component=shared,
    )

    result = resolve_required_capabilities(
        (_requirement("codec.json"),),
        _resolution(success, error),
    )

    # Lexical role selection labels the already-unique component; it does not
    # choose between providers or depend on input order.
    assert result.satisfied[0].provider_id == "codec.response.error-decoder"


def test_missing_required_capability_returns_stable_error() -> None:
    """Fail before execution when no selected Descriptor declares the required ID."""
    requirement = _requirement("model.tool.calling")
    unrelated = _selected("protocol.adapter", "plugin", "model.text.output")

    raised = cast(
        ModelInteractionError,
        _assert_raises(
            ModelInteractionError,
            lambda: resolve_required_capabilities(
                (requirement,),
                _resolution(unrelated),
            ),
            "required interaction capability is unsupported",
        ),
    )

    assert str(raised.category) == "unsupported_feature"
    assert str(raised.phase) == "capability_resolution"
    assert raised.code == "unsupported_capability"
    assert raised.status_code is None
    assert raised.service_error_code is None
    assert raised.request_id is None
    assert raised.recovery is None
    assert raised.cause is None
    assert "model.tool.calling" not in str(raised)
    assert "protocol.adapter" not in str(raised)


def test_nonempty_constraints_are_not_silently_ignored() -> None:
    """Reject required constraints that ID-only Descriptor facts cannot prove."""
    requirement = _requirement(
        "model.context.window",
        constraints={"minimumTokens": 128_000},
    )
    provider = _selected(
        "protocol.adapter",
        "plugin",
        "model.context.window",
    )

    raised = cast(
        ModelInteractionError,
        _assert_raises(
            ModelInteractionError,
            lambda: resolve_required_capabilities(
                (requirement,),
                _resolution(provider),
            ),
            "required interaction capability is unsupported",
        ),
    )

    assert raised.code == "unsupported_capability"
    assert "minimumTokens" not in str(raised)


def test_rejects_mutable_requirement_collection_and_wrong_snapshot() -> None:
    """Require the immutable tuple and nominal selected-component aggregate."""
    requirement = _requirement("model.text.output")

    _assert_raises(
        TypeError,
        lambda: resolve_required_capabilities(
            cast(tuple[CapabilityRequirement, ...], [requirement]),
            _resolution(),
        ),
        "requirements must be a tuple",
    )
    _assert_raises(
        TypeError,
        lambda: resolve_required_capabilities(
            (requirement,),
            cast(ComponentSelectionResolution, object()),
        ),
        "selected_components must be a ComponentSelectionResolution",
    )


def test_validates_complete_requirement_surface_before_filtering() -> None:
    """Reject partial and malformed requirements, including optional values."""
    incomplete = _IncompleteRequirement(OpenIdentifier("model.text.output"))
    malformed_cases: tuple[tuple[_MalformedRequirement, str], ...] = (
        (
            _MalformedRequirement("model.text.output", True, {}, None, {}),
            "capability_id must be an OpenIdentifier",
        ),
        (
            _MalformedRequirement(OpenIdentifier("model.text.output"), 1, {}, None, {}),
            "required must be a boolean",
        ),
        (
            _MalformedRequirement(
                OpenIdentifier("model.text.output"), False, [], None, {}
            ),
            "constraints must be a mapping",
        ),
        (
            _MalformedRequirement(
                OpenIdentifier("model.text.output"), False, {}, 1, {}
            ),
            "source_path must be a string or None",
        ),
        (
            _MalformedRequirement(
                OpenIdentifier("model.text.output"), False, {}, None, []
            ),
            "extensions must be a mapping",
        ),
    )

    _assert_raises(
        TypeError,
        lambda: resolve_required_capabilities(
            (cast(CapabilityRequirement, incomplete),),
            _resolution(),
        ),
        "must contain CapabilityRequirement values",
    )
    for malformed, message in malformed_cases:
        # required=False cases prove validation occurs before optional deferral.
        _assert_raises(
            TypeError,
            lambda malformed=malformed: resolve_required_capabilities(
                (cast(CapabilityRequirement, malformed),),
                _resolution(),
            ),
            message,
        )


def test_rejects_nonportable_constraint_and_extension_values() -> None:
    """Validate recursive JSON portability without interpreting mappings."""
    invalid_values: tuple[tuple[_Requirement, type[BaseException], str], ...] = (
        (
            _requirement(
                "model.text.output",
                required=False,
                constraints={"invalid": float("inf")},
            ),
            ValueError,
            "finite",
        ),
        (
            _Requirement(
                OpenIdentifier("model.text.output"),
                False,
                {},
                None,
                cast(Extensions, {"invalid": object()}),
            ),
            TypeError,
            "structurally valid JsonValue",
        ),
    )

    for requirement, exception_type, message in invalid_values:
        _assert_raises(
            exception_type,
            lambda requirement=requirement: resolve_required_capabilities(
                (requirement,),
                _resolution(),
            ),
            message,
        )
