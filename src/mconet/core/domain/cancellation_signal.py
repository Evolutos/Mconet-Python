"""Read-only cancellation state and subscription contract."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, runtime_checkable


@runtime_checkable
class CancellationSignal(Protocol):
    """Expose one idempotent cancellation transition to interaction consumers.

    A concrete source owns the operation that requests cancellation; this
    read-only contract only observes it. The first transition to cancelled wins
    and preserves its optional reason. Repeated cancellation requests must not
    replace that reason or notify a subscriber more than once.

    A subscriber registered before cancellation is called once when the first
    transition occurs. A subscriber registered after cancellation is called
    once with the preserved reason before ``subscribe`` returns. The returned
    unsubscribe function must itself be idempotent; after notification it is a
    no-op. Implementations must not share mutable cancellation state between
    independent interactions.
    """

    @property
    def is_cancelled(self) -> bool:
        """Return whether the first cancellation transition has occurred."""
        # Consumers can inspect pre-cancelled input before registering work or
        # performing any transport side effect.
        ...

    @property
    def reason(self) -> str | None:
        """Return the first cancellation reason, or None when absent or active."""
        # The reason remains stable after cancellation; later requests cannot
        # overwrite it with a different value.
        ...

    def subscribe(
        self,
        callback: Callable[[str | None], None],
    ) -> Callable[[], None]:
        """Register one cancellation callback and return an idempotent remover.

        Args:
            callback: Function called at most once with the preserved reason.

        Returns:
            A zero-argument function that removes a pending subscription. Calling
            it repeatedly or after notification has no additional effect.
        """
        # Concrete signals own synchronization and callback storage. The protocol
        # fixes observable lifecycle semantics without prescribing an event loop,
        # thread primitive, or network cancellation mechanism.
        ...
