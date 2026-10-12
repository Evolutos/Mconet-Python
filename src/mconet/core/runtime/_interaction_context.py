"""Internal context owned by exactly one model interaction."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast
from uuid import UUID, uuid4

from mconet.core.domain.error_category import ErrorCategory
from mconet.core.domain.interaction_phase import InteractionPhase
from mconet.core.domain.model_interaction_error import ModelInteractionError
from mconet.core.domain.model_request import ModelRequest
from mconet.core.domain.open_identifier import OpenIdentifier
from mconet.core.runtime.resolved_interaction_configuration import (
    ResolvedInteractionConfiguration,
)

_INTERNAL = ErrorCategory(OpenIdentifier("internal"))
_RUNTIME = InteractionPhase(OpenIdentifier("runtime"))
_RELEASED_CODE = "interaction_context_released"
_RELEASED_MESSAGE = "The interaction context has been released."


class InteractionContext:
    """Hold the inputs of one interaction without retaining them on a client.

    Construction always allocates a new context. The context keeps the request
    and the resolved configuration supplied for that interaction, plus an
    identity that belongs only to this allocation. It has no client field, no
    class-level registry, and no constructor argument that could attach it to a
    client. Two interactions therefore cannot share one context, even when they
    are given the same request and configuration objects.

    Callbacks and the request and configuration references are one-shot.
    ``release`` drops them after the interaction terminates. The identity
    remains so a released context can still be distinguished.

    This type stores references only. It does not normalize the request,
    validate task or message scope, resolve components, subscribe to
    cancellation, copy secrets, or execute I/O. Those stages consume a context
    later and must leave the context off any client.
    """

    __slots__ = (
        "_callbacks",
        "_configuration",
        "_identity",
        "_released",
        "_request",
    )

    def __init__(
        self,
        request: ModelRequest,
        configuration: ResolvedInteractionConfiguration,
    ) -> None:
        """Bind one request and one resolved configuration to a new context.

        Args:
            request: The model request that this interaction will execute.
            configuration: The immutable configuration selected for this
                interaction, including its optional cancellation signal.

        Raises:
            TypeError: If either argument violates its nominal storage contract.
        """
        request_value = cast(object, request)
        configuration_value = cast(object, configuration)
        # Structural requests stay open to custom envelopes. A non-request must
        # not become the identity of an interaction.
        if not isinstance(request_value, ModelRequest):
            raise TypeError("InteractionContext request must implement ModelRequest.")
        # Configuration is a concrete resolved value, not an open protocol, so
        # a client options object cannot be stored in its place.
        if not isinstance(configuration_value, ResolvedInteractionConfiguration):
            raise TypeError(
                "InteractionContext configuration must be "
                "ResolvedInteractionConfiguration."
            )

        # The identity comes from this allocation alone. Reusing the request or
        # configuration does not reuse the context, and nothing records the new
        # instance on a client or in a process-wide collection.
        self._request: ModelRequest | None = request_value
        self._configuration: ResolvedInteractionConfiguration | None = (
            configuration_value
        )
        self._identity = uuid4()
        self._callbacks: list[Callable[[], None]] = []
        self._released = False

    @property
    def request(self) -> ModelRequest:
        """Return the request bound to this interaction.

        Returns:
            The exact request supplied at construction.

        Raises:
            ModelInteractionError: If the context has been released.
        """
        # Expose the stored reference without copying it onto any other owner.
        return self._require_request()

    @property
    def configuration(self) -> ResolvedInteractionConfiguration:
        """Return the resolved configuration bound to this interaction.

        Returns:
            The exact configuration supplied at construction.

        Raises:
            ModelInteractionError: If the context has been released.
        """
        # The configuration remains interaction-scoped storage. Reading it does
        # not publish the context back to the client that produced the values.
        return self._require_configuration()

    @property
    def identity(self) -> UUID:
        """Return the identity that no other context allocation shares.

        Returns:
            The UUID created for this context alone.
        """
        # Identity distinguishes interactions. It is not derived from the
        # request, the configuration, or any client. Release does not change it.
        return self._identity

    @property
    def released(self) -> bool:
        """Return whether one-shot references have already been dropped."""
        return self._released

    @property
    def callback_count(self) -> int:
        """Return how many callbacks this context still holds."""
        return len(self._callbacks)

    def add_callback(self, callback: Callable[[], None]) -> None:
        """Register one callback that release will drop.

        Args:
            callback: Interaction-scoped listener. Release removes it and does
                not call it.

        Raises:
            TypeError: If ``callback`` is not callable.
            ModelInteractionError: If the context has been released.
        """
        callback_value = cast(object, callback)
        if self._released:
            raise _released_error()
        if not isinstance(callback_value, Callable):
            raise TypeError("callback must be callable.")
        self._callbacks.append(cast(Callable[[], None], callback_value))

    def release(self) -> None:
        """Drop callbacks and one-shot references after termination.

        A second call does nothing. Callbacks are not invoked. The identity
        remains.
        """
        if self._released:
            return
        # Drop the references before publishing the released flag so a reader
        # cannot observe released storage that still holds the request.
        self._request = None
        self._configuration = None
        self._callbacks.clear()
        self._released = True

    def _require_request(self) -> ModelRequest:
        """Return the request or fail once the context has been released."""
        request = self._request
        if request is None:
            raise _released_error()
        return request

    def _require_configuration(self) -> ResolvedInteractionConfiguration:
        """Return the configuration or fail once the context has been released."""
        configuration = self._configuration
        if configuration is None:
            raise _released_error()
        return configuration


def _released_error() -> ModelInteractionError:
    """Build the stable error for use of a released context."""
    return ModelInteractionError(
        category=_INTERNAL,
        phase=_RUNTIME,
        code=_RELEASED_CODE,
        message=_RELEASED_MESSAGE,
    )
