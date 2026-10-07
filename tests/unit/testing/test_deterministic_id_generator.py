"""Sequence and concurrency tests for DeterministicIdGenerator."""

from __future__ import annotations

import inspect
from concurrent.futures import ThreadPoolExecutor
from typing import get_type_hints

from mconet.testing import DeterministicIdGenerator


def test_generator_has_zero_argument_constructor_and_sync_string_result() -> None:
    """Expose one immediate identity request without configuration."""
    constructor = inspect.signature(DeterministicIdGenerator)
    next_id = DeterministicIdGenerator.next_id

    # The concrete Python spelling follows snake_case while retaining the shared
    # zero-input, synchronous string contract used by other implementations.
    assert tuple(constructor.parameters) == ()
    assert tuple(inspect.signature(next_id).parameters) == ("self",)
    assert get_type_hints(next_id) == {"return": str}
    assert not inspect.iscoroutinefunction(next_id)


def test_generator_emits_fixed_sequence_from_id_one() -> None:
    """Return the exact stable prefix and positive decimal progression."""
    generator = DeterministicIdGenerator()

    identifiers = (
        generator.next_id(),
        generator.next_id(),
        generator.next_id(),
    )

    # Exact values make snapshots and contract fixtures repeatable across runs.
    assert identifiers == ("id-1", "id-2", "id-3")


def test_generator_keeps_sequence_state_isolated_between_instances() -> None:
    """Prevent one fixture from consuming another fixture's identifiers."""
    first = DeterministicIdGenerator()
    second = DeterministicIdGenerator()

    # Both instances begin at the same deterministic value but advance only in
    # response to their own calls; no module-level counter couples test order.
    assert first.next_id() == "id-1"
    assert first.next_id() == "id-2"
    assert second.next_id() == "id-1"
    assert first.next_id() == "id-3"
    assert second.next_id() == "id-2"


def test_generator_produces_large_exact_ordered_batch() -> None:
    """Keep every sequential value unique without integer precision loss."""
    generator = DeterministicIdGenerator()

    identifiers = tuple(generator.next_id() for _ in range(10_000))

    # Selected boundaries and complete uniqueness verify increment behavior over
    # more than the single-digit range without relying on lexical sorting.
    assert len(set(identifiers)) == 10_000
    assert identifiers[0] == "id-1"
    assert identifiers[499] == "id-500"
    assert identifiers[9_999] == "id-10000"


def test_generator_reserves_every_concurrent_sequence_position_once() -> None:
    """Generate a gap-free unique set under concurrent callers."""
    generator = DeterministicIdGenerator()

    def generate(_: int) -> str:
        """Request one identity without imposing worker completion order."""
        # The ignored map index controls only task count; sequence allocation is
        # owned exclusively by the generator's atomic critical section.
        return generator.next_id()

    with ThreadPoolExecutor(max_workers=32) as executor:
        identifiers = tuple(executor.map(generate, range(5_000)))

    # Completion ordering is scheduler-owned, so compare the numeric membership
    # set. Every position is present once and the next call proves exact advance.
    sequence_numbers = {
        int(identifier.removeprefix("id-")) for identifier in identifiers
    }
    assert len(identifiers) == 5_000
    assert len(set(identifiers)) == 5_000
    assert sequence_numbers == set(range(1, 5_001))
    assert generator.next_id() == "id-5001"


def test_generator_exposes_no_sequence_controls_or_configuration() -> None:
    """Keep counter state private and the public behavior surface minimal."""
    generator = DeterministicIdGenerator()

    # Slots prevent an arbitrary instance dictionary, while ordinary public
    # controls that could make the same call count nondeterministic stay absent.
    assert not hasattr(generator, "__dict__")
    for forbidden_member in (
        "seed",
        "prefix",
        "current_id",
        "next_sequence",
        "reset",
        "peek",
        "set",
        "random",
    ):
        assert not hasattr(generator, forbidden_member)

    assert generator.next_id() == "id-1"
