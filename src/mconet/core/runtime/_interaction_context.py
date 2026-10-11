"""Internal context owned by exactly one model interaction."""

from __future__ import annotations

from typing import cast
from uuid import UUID, uuid4

from mconet.core.domain.model_request import ModelRequest
from mconet.core.runtime.resolved_interaction_configuration import (
    ResolvedInteractionConfiguration,
)


class InteractionContext:
    """Hold the inputs of one interaction without retaining them on a client.

    Construction always allocates a new context. The context keeps the request
    and the resolved configuration supplied for that interaction, plus an
    identity that belongs only to this allocation. It has no client field, no
    class-level registry, and no constructor argument that could attach it to a
    client. Two interactions therefore cannot share one context, even when they
    are given the same request and configuration objects.

    This type stores references only. It does not normalize the request,
    validate task or message scope, resolve components, subscribe to
    cancellation, copy secrets, or execute I/O. Those stages consume a context
    later and must leave the context off any client.
    """

    __slots__ = ("_configuration", "_identity", "_request")

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
        self._request = request
        self._configuration = configuration
        self._identity = uuid4()

    @property
    def request(self) -> ModelRequest:
        """Return the request bound to this interaction.

        Returns:
            The exact request supplied at construction.
        """
        # Expose the stored reference without copying it onto any other owner.
        return self._request

    @property
    def configuration(self) -> ResolvedInteractionConfiguration:
        """Return the resolved configuration bound to this interaction.

        Returns:
            The exact configuration supplied at construction.
        """
        # The configuration remains interaction-scoped storage. Reading it does
        # not publish the context back to the client that produced the values.
        return self._configuration

    @property
    def identity(self) -> UUID:
        """Return the identity that no other context allocation shares.

        Returns:
            The UUID created for this context alone.
        """
        # Identity distinguishes interactions. It is not derived from the
        # request, the configuration, or any client.
        return self._identity
