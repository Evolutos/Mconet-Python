"""Value and boundary tests for immutable component descriptors."""

from collections.abc import Callable
from dataclasses import FrozenInstanceError
from typing import Literal, cast

from mconet.core.domain import MediaType, OpenIdentifier
from mconet.core.spi import (
    ComponentDescriptor,
    ComponentTypeContract,
    ComponentTypePort,
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
        # Match stable descriptor wording so an unrelated runtime failure cannot
        # make a negative boundary test appear successful.
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def _type_contract() -> ComponentTypeContract:
    """Build one complete type contract for descriptor field tests."""
    # Distinct input and output types ensure the descriptor retains the complete
    # nested contract rather than substituting an empty default.
    return ComponentTypeContract(
        inputs=(
            ComponentTypePort(
                "requestPayload",
                OpenIdentifier("payload.request"),
                "schema://request",
                MediaType("application", "json"),
            ),
        ),
        outputs=(
            ComponentTypePort(
                "successPayload",
                OpenIdentifier("payload.success"),
                "schema://success",
                MediaType("application", "json"),
            ),
        ),
    )


def test_component_descriptor_preserves_all_declared_fields() -> None:
    """Verify every descriptor fact remains exact and independently observable."""
    type_contract = _type_contract()
    capabilities = frozenset(
        (
            OpenIdentifier("codec.json"),
            OpenIdentifier("vendor.structured_output"),
        )
    )

    descriptor = ComponentDescriptor(
        name="Vendor JSON Encoder",
        version="2026.10-preview",
        source="plugin",
        type_contract=type_contract,
        capabilities=capabilities,
    )

    # Exact values and identities prove construction neither normalizes labels
    # nor rebuilds the already immutable contract and capability set.
    assert descriptor.name == "Vendor JSON Encoder"
    assert descriptor.version == "2026.10-preview"
    assert descriptor.source == "plugin"
    assert descriptor.type_contract is type_contract
    assert descriptor.capabilities is capabilities


def test_component_descriptor_supports_each_source_and_no_port_contract() -> None:
    """Verify all provenance values and port-free component defaults are valid."""
    sources: tuple[Literal["builtin", "plugin", "application"], ...] = (
        "builtin",
        "plugin",
        "application",
    )

    # Resolver, handler, and monitor components can have no data ports while
    # provenance remains an explicit non-null fact.
    descriptors = tuple(
        ComponentDescriptor("component", "1", source) for source in sources
    )
    assert tuple(descriptor.source for descriptor in descriptors) == sources
    assert all(descriptor.type_contract is None for descriptor in descriptors)
    assert all(descriptor.capabilities == frozenset() for descriptor in descriptors)


def test_component_descriptor_has_immutable_value_semantics() -> None:
    """Verify equality, hashing, and frozen fields cover complete metadata."""
    capabilities = frozenset((OpenIdentifier("transport.http"),))
    first = ComponentDescriptor("HTTP", "1", "builtin", None, capabilities)
    same = ComponentDescriptor("HTTP", "1", "builtin", None, capabilities)
    application = ComponentDescriptor("HTTP", "1", "application", None, capabilities)

    # Provenance participates in value identity, and neither descriptor fields
    # nor capability membership can change after construction.
    assert first == same
    assert hash(first) == hash(same)
    assert first != application
    _assert_raises(
        FrozenInstanceError,
        lambda: first.__setattr__("version", "2"),
        "cannot assign to field",
    )
    assert not hasattr(first.capabilities, "add")


def test_component_descriptor_rejects_invalid_labels_and_source() -> None:
    """Verify diagnostic labels and provenance enforce declared primitives."""
    # Validate each primitive independently so dynamic callers receive a stable
    # field-specific failure at descriptor construction time.
    _assert_raises(
        TypeError,
        lambda: ComponentDescriptor(cast(str, 1), "1", "builtin"),
        "name must be a string",
    )
    _assert_raises(
        TypeError,
        lambda: ComponentDescriptor("component", cast(str, 1), "builtin"),
        "version must be a string",
    )
    _assert_raises(
        ValueError,
        lambda: ComponentDescriptor(
            "component",
            "1",
            cast(Literal["builtin", "plugin", "application"], "remote"),
        ),
        "source must be builtin, plugin, or application",
    )
    _assert_raises(
        TypeError,
        lambda: ComponentDescriptor(
            "component",
            "1",
            cast(Literal["builtin", "plugin", "application"], 1),
        ),
        "source must be a string",
    )


def test_component_descriptor_rejects_invalid_contract_and_capabilities() -> None:
    """Verify nested contract and capability collection keep nominal shapes."""
    # A mapping cannot replace the structured contract, and mutable or loosely
    # typed sets cannot become static capability declarations.
    _assert_raises(
        TypeError,
        lambda: ComponentDescriptor(
            "component",
            "1",
            "plugin",
            type_contract=cast(ComponentTypeContract, {}),
        ),
        "type_contract must be a ComponentTypeContract or None",
    )
    _assert_raises(
        TypeError,
        lambda: ComponentDescriptor(
            "component",
            "1",
            "plugin",
            capabilities=cast(frozenset[OpenIdentifier], set()),
        ),
        "capabilities must be a frozenset",
    )
    _assert_raises(
        TypeError,
        lambda: ComponentDescriptor(
            "component",
            "1",
            "plugin",
            capabilities=cast(frozenset[OpenIdentifier], frozenset(("codec",))),
        ),
        "capabilities must contain OpenIdentifier values",
    )
