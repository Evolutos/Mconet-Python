"""Contract tests for optional runtime component resource cleanup."""

from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass, field
from typing import get_type_hints

from mconet.core.spi import (
    CloseableRuntimeComponent,
    ComponentDescriptor,
    RuntimeComponent,
)


@dataclass(slots=True)
class _ExternalResource:
    """Application-owned dependency that component cleanup must preserve."""

    close_calls: int = 0
    """Observable release count retained as external-ownership evidence."""

    def close(self) -> None:
        """Record an invalid attempt to release the external dependency."""
        # The compliant component intentionally never calls this method; a count
        # makes accidental ownership transfer visible without a real I/O handle.
        self.close_calls += 1


@dataclass(slots=True)
class _CloseableComponent:
    """Resource-owning component implementing idempotent asynchronous cleanup."""

    descriptor: ComponentDescriptor
    """Static metadata required by the base runtime component boundary."""

    external_resource: _ExternalResource
    """Injected dependency whose lifecycle remains application-owned."""

    owned_release_calls: int = 0
    """Count of releases performed for the component's own resource."""

    _closed: bool = False
    """Private terminal state guarding repeated release effects."""

    _close_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    """Serialize concurrent callers around the single close transition."""

    async def close(self) -> None:
        """Release the owned resource once and preserve injected dependencies."""
        # The lock makes concurrent calls observe one state transition instead of
        # racing two releases of the same component-owned resource.
        async with self._close_lock:
            if self._closed:
                return

            # Mark the observable owned release and terminal state together. The
            # external dependency is deliberately untouched because its creator
            # retains responsibility for its lifecycle.
            self.owned_release_calls += 1
            self._closed = True


@dataclass(frozen=True, slots=True)
class _StatelessComponent:
    """Ordinary runtime component with no resource lifecycle operation."""

    descriptor: ComponentDescriptor
    """The only member required for stateless component participation."""


def _accept_closeable(
    component: CloseableRuntimeComponent,
) -> CloseableRuntimeComponent:
    """Cross the statically checked closeable component protocol boundary."""
    # Pyright proves ordinary structural implementations need no SDK base class,
    # registration identifier, ownership field, or lifecycle wrapper.
    return component


def test_closeable_component_refines_runtime_component_structurally() -> None:
    """Accept a resource owner without weakening the metadata boundary."""
    component = _CloseableComponent(
        ComponentDescriptor("SDK transport", "1", "builtin"),
        _ExternalResource(),
    )

    accepted = _accept_closeable(component)

    # Runtime and closeable protocol checks agree on the same exact application
    # object; no inheritance, adapter, registry, or copied descriptor is needed.
    assert accepted is component
    assert isinstance(component, RuntimeComponent)
    assert isinstance(component, CloseableRuntimeComponent)
    assert accepted.descriptor is component.descriptor


def test_close_is_async_idempotent_and_preserves_external_resource() -> None:
    """Perform one owned release across concurrent and repeated close calls."""
    external_resource = _ExternalResource()
    component = _CloseableComponent(
        ComponentDescriptor("SDK transport", "1", "builtin"),
        external_resource,
    )

    async def close_repeatedly() -> None:
        """Exercise overlapping callers followed by one terminal-state call."""
        # Concurrent requests verify the internal transition cannot duplicate the
        # owned release; the final call verifies the completed state is reusable.
        await asyncio.gather(component.close(), component.close())
        await component.close()

    asyncio.run(close_repeatedly())

    # Only the component-owned resource is released. The injected dependency is
    # still available to the application after every idempotent close attempt.
    assert component.owned_release_calls == 1
    assert external_resource.close_calls == 0


def test_stateless_runtime_component_needs_no_close_method() -> None:
    """Keep lifecycle participation optional for components without resources."""
    component = _StatelessComponent(
        ComponentDescriptor("Stateless codec", "1", "application")
    )

    # The minimal component contract stays descriptor-only; adding the optional
    # refinement cannot force no-op lifecycle methods onto codecs and adapters.
    assert isinstance(component, RuntimeComponent)
    assert not isinstance(component, CloseableRuntimeComponent)
    assert not hasattr(component, "close")


def test_closeable_contract_exposes_only_async_close_behavior() -> None:
    """Lock the lifecycle surface to one argument-free asynchronous operation."""
    close = CloseableRuntimeComponent.close

    # Ownership classification, component collections, cancellation policy, and
    # monitoring are deliberately absent from the component-owned operation.
    assert tuple(inspect.signature(close).parameters) == ("self",)
    assert get_type_hints(close) == {"return": type(None)}
    assert inspect.iscoroutinefunction(close)
    assert not hasattr(CloseableRuntimeComponent, "aclose")
    assert not hasattr(CloseableRuntimeComponent, "is_closed")


def test_runtime_component_remains_free_of_lifecycle_behavior() -> None:
    """Prevent the optional close contract from expanding every component SPI."""
    members = frozenset(name for name, _ in inspect.getmembers(RuntimeComponent))

    # Lifecycle is selected through structural refinement after ownership is
    # known; the universal metadata protocol still cannot close any component.
    assert "descriptor" in members
    assert "close" not in members
    assert "aclose" not in members
