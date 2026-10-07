"""Layering tests for deterministic internal component source merging."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import FrozenInstanceError, dataclass, fields
from typing import cast

from mconet.core.runtime._component_source_merge import merge_component_sources
from mconet.core.spi import (
    AuthorizationHandler,
    AuthorizationHandlerResolver,
    ComponentDescriptor,
    ModelIntegrationMatch,
    ModelIntegrationPlan,
    ModelIntegrationResolver,
    ModelTargetMatch,
    PayloadDecoder,
    PayloadEncoder,
    RuntimeComponent,
    RuntimeComponents,
    ServiceAccessResolver,
    TaskMatch,
    TaskProtocolAdapter,
    Transport,
)


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    try:
        action()
    except exception_type as error:
        # Stable parameter-owned wording proves input normalization, rather than
        # arbitrary later attribute access, rejected the malformed source layer.
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


@dataclass(frozen=True, slots=True)
class _Component:
    """Distinguishable component fixture requiring no role behavior methods."""

    descriptor: ComponentDescriptor
    """Immutable metadata satisfying the common runtime component boundary."""


def _component(name: str) -> _Component:
    """Build one concrete component fixture with stable diagnostic metadata."""
    # Unique instances and names make source order, exact identity, duplicates,
    # and accidental role swaps independently visible in assertions.
    return _Component(ComponentDescriptor(name, "1.0.0", "application"))


def _plan(
    adapter: _Component,
    *,
    handlers: tuple[_Component, ...] = (),
    encoders: tuple[_Component, ...] = (),
    decoders: tuple[_Component, ...] = (),
    transports: tuple[_Component, ...] = (),
) -> ModelIntegrationPlan:
    """Build one plan carrying optional integration-layer candidates."""
    # A resolved-binding plan owns integration candidates. Complete successful
    # match facts keep this fixture inside the same validated construction path as
    # production resolver output even though scores do not affect source merging.
    if handlers or encoders or decoders or transports:
        return ModelIntegrationPlan(
            "resolved_binding",
            "fixture",
            "1.0.0",
            ModelIntegrationMatch(
                ModelTargetMatch(True, 100),
                TaskMatch(True, 100),
            ),
            cast(RuntimeComponent, adapter),
            tuple(cast(RuntimeComponent, item) for item in handlers),
            None,
            tuple(cast(RuntimeComponent, item) for item in encoders),
            tuple(cast(RuntimeComponent, item) for item in decoders),
            tuple(cast(RuntimeComponent, item) for item in transports),
        )
    return ModelIntegrationPlan(
        "direct_adapter",
        None,
        None,
        None,
        cast(RuntimeComponent, adapter),
    )


def _components(
    prefix: str,
    *,
    handlers: tuple[_Component, ...] = (),
) -> tuple[RuntimeComponents, tuple[_Component, ...]]:
    """Build one fully populated direct component source layer."""
    # One distinct fixture per field makes the field mapping independently
    # observable while the typed carrier intentionally performs no role calls.
    integration_resolver = _component(f"{prefix}-integration-resolver")
    adapter = _component(f"{prefix}-adapter")
    access_resolver = _component(f"{prefix}-access-resolver")
    encoder = _component(f"{prefix}-encoder")
    success_decoder = _component(f"{prefix}-success-decoder")
    error_decoder = _component(f"{prefix}-error-decoder")
    transport = _component(f"{prefix}-transport")
    authorization_resolver = _component(f"{prefix}-authorization-resolver")
    components = RuntimeComponents(
        model_integration_resolver=cast(
            ModelIntegrationResolver,
            integration_resolver,
        ),
        task_protocol_adapter=cast(TaskProtocolAdapter, adapter),
        service_access_resolver=cast(ServiceAccessResolver, access_resolver),
        payload_encoder=cast(PayloadEncoder, encoder),
        success_payload_decoder=cast(PayloadDecoder, success_decoder),
        error_payload_decoder=cast(PayloadDecoder, error_decoder),
        transport=cast(Transport, transport),
        authorization_handler_resolver=cast(
            AuthorizationHandlerResolver,
            authorization_resolver,
        ),
        authorization_handlers=tuple(
            cast(AuthorizationHandler, handler) for handler in handlers
        ),
    )
    return components, (
        integration_resolver,
        adapter,
        access_resolver,
        encoder,
        success_decoder,
        error_decoder,
        transport,
        authorization_resolver,
        *handlers,
    )


def test_merge_preserves_all_four_single_value_source_layers() -> None:
    """Retain candidates in interaction, Client, integration, default order."""
    interaction, interaction_values = _components("interaction")
    client, client_values = _components("client")
    defaults, default_values = _components("default")
    binding_adapter = _component("binding-adapter")
    binding_encoder = _component("binding-encoder")
    first_binding_decoder = _component("binding-first-decoder")
    second_binding_decoder = _component("binding-second-decoder")
    binding_transport = _component("binding-transport")
    integration_plan = _plan(
        binding_adapter,
        encoders=(binding_encoder,),
        decoders=(first_binding_decoder, second_binding_decoder),
        transports=(binding_transport,),
    )

    merged = merge_component_sources(
        interaction,
        client,
        integration_plan,
        defaults,
    )

    # Outer tuple positions are the fixed priority contract. Inner tuples retain
    # same-layer multiplicity so the next selector can detect ambiguity itself.
    assert merged.task_protocol_adapter == (
        (interaction_values[1],),
        (client_values[1],),
        (binding_adapter,),
        (default_values[1],),
    )
    assert merged.payload_encoder == (
        (interaction_values[3],),
        (client_values[3],),
        (binding_encoder,),
        (default_values[3],),
    )
    assert merged.success_payload_decoder == (
        (interaction_values[4],),
        (client_values[4],),
        (first_binding_decoder, second_binding_decoder),
        (default_values[4],),
    )
    assert merged.error_payload_decoder == (
        (interaction_values[5],),
        (client_values[5],),
        (first_binding_decoder, second_binding_decoder),
        (default_values[5],),
    )
    assert merged.transport == (
        (interaction_values[6],),
        (client_values[6],),
        (binding_transport,),
        (default_values[6],),
    )


def test_merge_preserves_empty_integration_layers_for_remaining_resolvers() -> None:
    """Keep resolver precedence structural when no Binding source exists."""
    interaction, interaction_values = _components("interaction")
    client, client_values = _components("client")
    defaults, default_values = _components("default")
    integration_plan = _plan(_component("binding-adapter"))

    merged = merge_component_sources(
        interaction,
        client,
        integration_plan,
        defaults,
    )

    # Access and authorization resolver lookup has no Binding-provided role. The
    # empty third tuple prevents the default layer from being mistaken for it.
    assert merged.service_access_resolver == (
        (interaction_values[2],),
        (client_values[2],),
        (),
        (default_values[2],),
    )
    assert merged.authorization_handler_resolver == (
        (interaction_values[7],),
        (client_values[7],),
        (),
        (default_values[7],),
    )


def test_merge_appends_handler_candidates_without_deduplication_or_sorting() -> None:
    """Combine every handler layer while retaining exact identity and order."""
    shared = _component("shared-handler")
    interaction_handler = _component("z-interaction-handler")
    client_handler = _component("a-client-handler")
    binding_handler = _component("binding-handler")
    default_handler = _component("default-handler")
    interaction, _ = _components(
        "interaction",
        handlers=(interaction_handler, shared),
    )
    client, _ = _components("client", handlers=(client_handler, shared))
    defaults, _ = _components("default", handlers=(default_handler,))
    integration_plan = _plan(
        _component("binding-adapter"),
        handlers=(binding_handler,),
    )

    merged = merge_component_sources(
        interaction,
        client,
        integration_plan,
        defaults,
    )

    # Duplicate identity remains visible to the dedicated resolver, and lexical
    # names cannot reorder candidates or become hidden component identifiers.
    assert merged.authorization_handlers == (
        interaction_handler,
        shared,
        client_handler,
        shared,
        binding_handler,
        default_handler,
    )
    assert merged.authorization_handlers[1] is shared
    assert merged.authorization_handlers[3] is shared


def test_merge_normalizes_absent_direct_layers_without_collapsing_priority() -> None:
    """Represent absent Interaction and Client inputs as explicit empty layers."""
    default_encoder = _component("default-encoder")
    defaults = RuntimeComponents(
        payload_encoder=cast(PayloadEncoder, default_encoder),
    )
    binding_adapter = _component("binding-adapter")
    binding_encoder = _component("binding-encoder")
    integration_plan = _plan(binding_adapter, encoders=(binding_encoder,))

    merged = merge_component_sources(None, None, integration_plan, defaults)

    # Four positions always mean the same sources, even when the two highest
    # layers and most default roles contribute no candidates.
    assert merged.payload_encoder == (
        (),
        (),
        (binding_encoder,),
        (default_encoder,),
    )
    assert merged.task_protocol_adapter == ((), (), (binding_adapter,), ())
    assert merged.transport == ((), (), (), ())
    assert merged.authorization_handlers == ()


def test_merge_result_is_an_immutable_internal_source_snapshot() -> None:
    """Freeze field membership without publishing lookup or selection methods."""
    defaults = RuntimeComponents()
    merged = merge_component_sources(
        None,
        None,
        _plan(_component("binding-adapter")),
        defaults,
    )

    # The explicit role surface prevents a generic component map, while frozen
    # fields and nested tuples prevent source membership or order replacement.
    assert tuple(field.name for field in fields(merged)) == (
        "task_protocol_adapter",
        "service_access_resolver",
        "payload_encoder",
        "success_payload_decoder",
        "error_payload_decoder",
        "transport",
        "authorization_handler_resolver",
        "authorization_handlers",
    )
    assert not hasattr(merged, "__dict__")
    assert not hasattr(merged, "registry")
    assert not hasattr(merged, "component_ids")
    assert not hasattr(merged, "select")
    assert not hasattr(merged, "resolve")
    _assert_raises(
        FrozenInstanceError,
        lambda: merged.__setattr__("transport", ((), (), (), ())),
        "cannot assign to field",
    )


def test_merge_rejects_malformed_source_containers_at_the_boundary() -> None:
    """Reject arbitrary dynamic objects instead of treating them as role maps."""
    plan = _plan(_component("binding-adapter"))
    defaults = RuntimeComponents()

    # Each parameter has one nominal carrier type. Stable errors prevent a dict
    # or lookalike object from becoming an undocumented configuration extension.
    _assert_raises(
        TypeError,
        lambda: merge_component_sources(
            cast(RuntimeComponents, {}),
            None,
            plan,
            defaults,
        ),
        "interaction_components must be RuntimeComponents or None",
    )
    _assert_raises(
        TypeError,
        lambda: merge_component_sources(
            None,
            cast(RuntimeComponents, object()),
            plan,
            defaults,
        ),
        "client_components must be RuntimeComponents or None",
    )
    _assert_raises(
        TypeError,
        lambda: merge_component_sources(
            None,
            None,
            cast(ModelIntegrationPlan, object()),
            defaults,
        ),
        "integration_plan must be a ModelIntegrationPlan",
    )
    _assert_raises(
        TypeError,
        lambda: merge_component_sources(
            None,
            None,
            plan,
            cast(RuntimeComponents, object()),
        ),
        "sdk_defaults must be RuntimeComponents",
    )
