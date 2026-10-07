"""Tests for deterministic runtime component lifecycle ownership decisions."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, cast

from mconet.core.runtime._component_ownership import (
    determine_component_ownership,
)
from mconet.core.spi import (
    AuthorizationHandler,
    AuthorizationHandlerResolver,
    ComponentDescriptor,
    ModelIntegrationResolver,
    PayloadDecoder,
    PayloadEncoder,
    RuntimeComponent,
    RuntimeComponents,
    ServiceAccessResolver,
    TaskProtocolAdapter,
    Transport,
)


@dataclass(slots=True)
class _Component:
    """Runtime component fixture with observable but forbidden close behavior."""

    descriptor: ComponentDescriptor
    """Nominal metadata whose source must not determine ownership."""

    close_calls: int = 0
    """Count proving ownership classification never performs lifecycle actions."""

    def close(self) -> None:
        """Record a close call that ownership determination must never make."""
        # A synchronous method is sufficient as a side-effect canary; the later
        # close contract owns actual sync/async lifecycle behavior.
        self.close_calls += 1


@dataclass(frozen=True, slots=True)
class _MalformedComponent:
    """Component-shaped fixture exposing non-nominal descriptor metadata."""

    descriptor: object
    """Invalid dynamic metadata retained for boundary rejection tests."""


def _component(
    name: str,
    source: Literal["builtin", "plugin", "application"] = "plugin",
) -> _Component:
    """Create a distinct component with configurable descriptor provenance."""
    # Descriptors may compare equal across instances, so names are intentionally
    # caller-controlled for both identity and equality regression tests.
    return _Component(ComponentDescriptor(name, "1", source))


def _in_field(field_name: str, component: _Component) -> RuntimeComponents:
    """Place one exact fixture into any supported RuntimeComponents field."""
    # Explicit branches retain static role types and make the complete carrier
    # surface visible without a dynamic attribute bag or mutation after creation.
    if field_name == "model_integration_resolver":
        return RuntimeComponents(
            model_integration_resolver=cast(ModelIntegrationResolver, component)
        )
    if field_name == "task_protocol_adapter":
        return RuntimeComponents(
            task_protocol_adapter=cast(TaskProtocolAdapter, component)
        )
    if field_name == "service_access_resolver":
        return RuntimeComponents(
            service_access_resolver=cast(ServiceAccessResolver, component)
        )
    if field_name == "payload_encoder":
        return RuntimeComponents(payload_encoder=cast(PayloadEncoder, component))
    if field_name == "success_payload_decoder":
        return RuntimeComponents(
            success_payload_decoder=cast(PayloadDecoder, component)
        )
    if field_name == "error_payload_decoder":
        return RuntimeComponents(error_payload_decoder=cast(PayloadDecoder, component))
    if field_name == "transport":
        return RuntimeComponents(transport=cast(Transport, component))
    if field_name == "authorization_handler_resolver":
        return RuntimeComponents(
            authorization_handler_resolver=cast(
                AuthorizationHandlerResolver,
                component,
            )
        )
    if field_name == "authorization_handlers":
        return RuntimeComponents(
            authorization_handlers=(cast(AuthorizationHandler, component),)
        )
    raise AssertionError(f"Unknown fixture field: {field_name}")


def _determine(
    component: RuntimeComponent,
    *,
    interaction: RuntimeComponents | None = None,
    client: RuntimeComponents | None = None,
    defaults: RuntimeComponents | None = None,
) -> str:
    """Return ownership text through one explicit production invocation."""
    # The helper supplies an empty nominal SDK carrier by default; production
    # itself still rejects an explicit None passed as required sdk_defaults.
    sdk_defaults = RuntimeComponents() if defaults is None else defaults
    return str(
        determine_component_ownership(
            component,
            interaction_components=interaction,
            client_components=client,
            sdk_defaults=sdk_defaults,
        )
    )


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require one ownership call to fail at the intended stable boundary."""
    try:
        action()
    except exception_type as error:
        # Stable text distinguishes the target boundary from incidental fixture
        # construction or protocol failures.
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_sdk_default_instance_is_builtin_owned() -> None:
    """Classify an exact SDK-default instance as builtin lifecycle ownership."""
    component = _component("sdk-default")

    result = _determine(component, defaults=_in_field("transport", component))

    # Exact SDK membership is the sole positive proof for builtin ownership;
    # Descriptor source remains plugin and is deliberately irrelevant.
    assert result == "builtin"
    assert component.descriptor.source == "plugin"
    assert component.close_calls == 0


def test_direct_interaction_and_client_instances_are_application_owned() -> None:
    """Classify both direct application injection scopes without SDK ownership."""
    interaction_component = _component("interaction")
    client_component = _component("client")

    interaction_result = _determine(
        interaction_component,
        interaction=_in_field("payload_encoder", interaction_component),
    )
    client_result = _determine(
        client_component,
        client=_in_field("payload_encoder", client_component),
    )

    # Both direct injection scopes represent explicit external lifecycle control
    # and therefore share one application ownership value.
    assert interaction_result == "application"
    assert client_result == "application"


def test_direct_injection_overrides_alias_in_sdk_defaults() -> None:
    """Keep one aliased direct instance application-owned despite SDK membership."""
    shared = _component("shared")

    result = _determine(
        shared,
        interaction=_in_field("transport", shared),
        defaults=_in_field("transport", shared),
    )

    # Application scopes are inspected first by identity so SDK defaults cannot
    # reclaim a caller-injected alias and close it later.
    assert result == "application"
    assert shared.close_calls == 0


def test_unlisted_binding_or_plugin_instance_defaults_to_application() -> None:
    """Conservatively retain externally sourced untracked component ownership."""
    binding_component = _component("binding", "plugin")

    result = _determine(binding_component)

    # Without exact SDK-default membership the runtime cannot prove creation
    # authority, so the safe result prevents accidental resource release.
    assert result == "application"


def test_descriptor_source_never_determines_ownership() -> None:
    """Separate lifecycle origin from builtin, plugin, and application metadata."""
    source_values: tuple[Literal["builtin", "plugin", "application"], ...] = (
        "builtin",
        "plugin",
        "application",
    )

    for source in source_values:
        sdk_component = _component(f"sdk:{source}", source)
        external_component = _component(f"external:{source}", source)

        # The same descriptor source produces opposite ownership when exact
        # creation-scope membership changes, proving no source-to-owner mapping.
        assert (
            _determine(
                sdk_component,
                defaults=_in_field("transport", sdk_component),
            )
            == "builtin"
        )
        assert _determine(external_component) == "application"


def test_ownership_matching_uses_identity_not_value_equality() -> None:
    """Do not grant builtin ownership to an equal but different component object."""
    sdk_component = _component("equal")
    equal_external = _component("equal")
    assert sdk_component == equal_external
    assert sdk_component is not equal_external

    result = _determine(
        equal_external,
        defaults=_in_field("transport", sdk_component),
    )

    # Descriptor and dataclass equality cannot establish resource creation or
    # ownership; only the retained SDK object itself is builtin-owned.
    assert result == "application"


def test_every_runtime_components_field_participates_in_identity_matching() -> None:
    """Recognize exact SDK ownership across all direct component carrier fields."""
    field_names = (
        "model_integration_resolver",
        "task_protocol_adapter",
        "service_access_resolver",
        "payload_encoder",
        "success_payload_decoder",
        "error_payload_decoder",
        "transport",
        "authorization_handler_resolver",
        "authorization_handlers",
    )

    for field_name in field_names:
        component = _component(f"sdk:{field_name}")

        # Each explicit RuntimeComponents field is an ownership source; the list
        # role preserves the same identity semantics as every single-value role.
        assert (
            _determine(component, defaults=_in_field(field_name, component))
            == "builtin"
        )


def test_ownership_determination_invokes_no_component_lifecycle_behavior() -> None:
    """Inspect immutable membership without closing or otherwise invoking components."""
    target = _component("target")
    unrelated = _component("unrelated")

    result = _determine(
        target,
        client=_in_field("transport", unrelated),
        defaults=_in_field("transport", target),
    )

    # The target is found after validating an unrelated direct candidate, yet
    # neither component's lifecycle can be touched during pure classification.
    assert result == "builtin"
    assert target.close_calls == 0
    assert unrelated.close_calls == 0


def test_ownership_determination_validates_all_inputs_before_matching() -> None:
    """Reject malformed targets, carriers, collections, and shadowed candidates."""
    target = _component("target")
    malformed = _MalformedComponent(descriptor=object())
    mutable_handlers = RuntimeComponents(
        authorization_handlers=cast(
            tuple[AuthorizationHandler, ...],
            [cast(AuthorizationHandler, target)],
        )
    )
    malformed_handler = RuntimeComponents(
        authorization_handlers=(cast(AuthorizationHandler, malformed),)
    )

    invalid_calls: tuple[tuple[Callable[[], object], str], ...] = (
        (
            lambda: determine_component_ownership(
                cast(RuntimeComponent, object()),
                interaction_components=None,
                client_components=None,
                sdk_defaults=RuntimeComponents(),
            ),
            "component must implement RuntimeComponent",
        ),
        (
            lambda: determine_component_ownership(
                target,
                interaction_components=cast(RuntimeComponents, object()),
                client_components=None,
                sdk_defaults=RuntimeComponents(),
            ),
            "interaction_components must be a RuntimeComponents or None",
        ),
        (
            lambda: determine_component_ownership(
                target,
                interaction_components=None,
                client_components=None,
                sdk_defaults=cast(RuntimeComponents, None),
            ),
            "sdk_defaults must be a RuntimeComponents",
        ),
        (
            lambda: determine_component_ownership(
                target,
                interaction_components=mutable_handlers,
                client_components=None,
                sdk_defaults=RuntimeComponents(),
            ),
            "authorization_handlers must be a tuple",
        ),
        (
            lambda: determine_component_ownership(
                target,
                interaction_components=malformed_handler,
                client_components=None,
                sdk_defaults=_in_field("transport", target),
            ),
            "interaction_components descriptor must be a ComponentDescriptor",
        ),
    )

    for action, message in invalid_calls:
        # Full source validation occurs before matching, so even malformed
        # application candidates shadowed by an SDK match cannot be ignored.
        _assert_raises(TypeError, action, message)


def test_ownership_determination_signature_has_no_inference_or_close_controls() -> None:
    """Expose exact source facts without descriptor or lifecycle policy switches."""
    signature = inspect.signature(determine_component_ownership)

    # The target is positional; all creation scopes are explicit keyword-only
    # inputs. No caller can force an answer or request a close side effect.
    assert tuple(signature.parameters) == (
        "component",
        "interaction_components",
        "client_components",
        "sdk_defaults",
    )
    assert (
        signature.parameters["component"].kind
        is inspect.Parameter.POSITIONAL_OR_KEYWORD
    )
    assert all(
        signature.parameters[name].kind is inspect.Parameter.KEYWORD_ONLY
        for name in (
            "interaction_components",
            "client_components",
            "sdk_defaults",
        )
    )
    for forbidden in (
        "descriptor_source",
        "component_name",
        "component_id",
        "ownership_override",
        "close",
        "release",
        "transfer",
    ):
        assert forbidden not in signature.parameters
