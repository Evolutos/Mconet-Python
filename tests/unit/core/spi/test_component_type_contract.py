"""Immutable collection tests for component type contracts."""

from collections.abc import Callable
from dataclasses import FrozenInstanceError
from typing import cast

from mconet.core.domain import MediaType, OpenIdentifier
from mconet.core.spi import ComponentTypeContract, ComponentTypePort


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    try:
        action()
    except exception_type as error:
        # Match a stable field-specific fragment so an unrelated exception
        # cannot accidentally satisfy a negative collection test.
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def _port(name: str, type_id: str) -> ComponentTypePort:
    """Build one valid port with distinguishable contract metadata."""
    # Include both optional values so collection tests exercise complete ports
    # rather than relying only on their minimal constructor form.
    return ComponentTypePort(
        name=name,
        type_id=OpenIdentifier(type_id),
        schema_id=f"schema://{name}",
        media_type=MediaType("application", "json"),
    )


def test_component_type_contract_preserves_direction_and_order() -> None:
    """Verify input and output tuples remain separate and exactly ordered."""
    request = _port("requestPayload", "payload.request")
    context = _port("context", "runtime.context")
    success = _port("successPayload", "payload.success")
    error = _port("errorPayload", "payload.error")
    inputs = (request, context)
    outputs = (success, error)

    contract = ComponentTypeContract(inputs=inputs, outputs=outputs)

    # Identity and element checks prove construction neither copies nor sorts
    # tuples and never merges the two directional namespaces.
    assert contract.inputs is inputs
    assert contract.outputs is outputs
    assert contract.inputs == (request, context)
    assert contract.outputs == (success, error)


def test_component_type_contract_defaults_to_empty_immutable_directions() -> None:
    """Verify components without declared ports receive independent directions."""
    contract = ComponentTypeContract()

    # Empty tuples express the absence of ports without mutable default state or
    # a nullable collection that every resolver would need to special-case.
    assert contract.inputs == ()
    assert contract.outputs == ()
    assert isinstance(contract.inputs, tuple)
    assert isinstance(contract.outputs, tuple)


def test_component_type_contract_has_immutable_value_semantics() -> None:
    """Verify equality, hashing, and frozen fields include both directions."""
    input_port = _port("input", "payload.input")
    output_port = _port("output", "payload.output")
    first = ComponentTypeContract((input_port,), (output_port,))
    same = ComponentTypeContract((input_port,), (output_port,))
    reversed_directions = ComponentTypeContract((output_port,), (input_port,))

    # Directional membership participates in value identity, and frozen fields
    # prevent replacing either complete tuple after resolver selection.
    assert first == same
    assert hash(first) == hash(same)
    assert first != reversed_directions
    _assert_raises(
        FrozenInstanceError,
        lambda: first.__setattr__("inputs", ()),
        "cannot assign to field",
    )


def test_component_type_contract_rejects_mutable_direction_collections() -> None:
    """Verify both input and output membership must use immutable tuples."""
    port = _port("payload", "payload.value")

    # Validate directions separately so neither one can admit a list merely
    # because the opposite direction already satisfies its tuple contract.
    _assert_raises(
        TypeError,
        lambda: ComponentTypeContract(
            inputs=cast(tuple[ComponentTypePort, ...], [port])
        ),
        "inputs must be a tuple",
    )
    _assert_raises(
        TypeError,
        lambda: ComponentTypeContract(
            outputs=cast(tuple[ComponentTypePort, ...], [port])
        ),
        "outputs must be a tuple",
    )


def test_component_type_contract_rejects_invalid_direction_members() -> None:
    """Verify both directional tuples contain only complete port values."""
    invalid = cast(tuple[ComponentTypePort, ...], ("payload",))

    # A string cannot stand in for a port because it omits type, schema, and
    # media metadata required by later compatibility checks.
    _assert_raises(
        TypeError,
        lambda: ComponentTypeContract(inputs=invalid),
        "inputs must contain ComponentTypePort values",
    )
    _assert_raises(
        TypeError,
        lambda: ComponentTypeContract(outputs=invalid),
        "outputs must contain ComponentTypePort values",
    )
