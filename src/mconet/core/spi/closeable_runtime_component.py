"""Optional asynchronous lifecycle contract for resource-owning components."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from mconet.core.spi.runtime_component import RuntimeComponent


@runtime_checkable
class CloseableRuntimeComponent(RuntimeComponent, Protocol):
    """Release resources owned by one runtime component exactly once.

    Stateless components implement only :class:`RuntimeComponent`. A component
    implements this refinement when it owns resources whose lifetime can extend
    beyond one behavior call, such as a connection pool, channel, worker, or
    monitoring exporter. ``close`` is asynchronous so cleanup can complete
    without a second synchronous lifecycle path.

    Implementations must make concurrent and repeated calls idempotent. Once one
    call begins, later calls must not start another release of the same resource;
    they either await the same completion or observe the already-closed state.
    A cleanup failure propagates to the lifecycle caller and does not authorize a
    second release attempt; later calls may repeat that failure or return from a
    terminal closed state, but must not duplicate cleanup side effects.
    Cleanup must release only resources owned by the component. A dependency
    injected into the component with external ownership must remain open.

    Runtime applies this operation only to exact component instances classified
    with ``builtin`` ownership. It must not invoke ``close`` for ``application``
    or unknown ownership values, even when such a component satisfies this
    protocol. When one instance fills multiple roles or appears in multiple
    execution snapshots, Runtime de-duplicates it by object identity before
    closing it.

    This contract does not decide ownership, stop new client requests, cancel
    active interactions, order unrelated component shutdown, suppress cleanup
    failures, or publish monitoring events. Those responsibilities belong to
    their dedicated runtime and client lifecycle steps.
    """

    async def close(self) -> None:
        """Release this component's owned resources idempotently."""
        # The awaitable result gives network and monitoring resources one common
        # completion boundary; callers never infer completion from object state.
        ...
