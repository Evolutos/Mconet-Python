"""Public interaction entry that R1 limits to one unary call."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from mconet.core.domain.model_output import ModelOutput
from mconet.core.domain.model_request import ModelRequest
from mconet.core.spi.interaction_options import InteractionOptions


@runtime_checkable
class ModelInteractor(Protocol):
    """Perform one unary model interaction.

    This protocol exposes only :meth:`interact`, which is one unary call.
    Server-stream consumption is :meth:`ModelClient.interact_server_stream`,
    not a method of this protocol. Client streaming, duplex, and long-running
    operations remain absent.
    The method receives one complete request and one interaction option value.
    It does not define a second pipeline, a client registry, or component
    identifiers.
    """

    async def interact(
        self,
        request: ModelRequest,
        options: InteractionOptions,
    ) -> ModelOutput:
        """Run one unary interaction and return its assembled output.

        Args:
            request: Complete model request for this interaction.
            options: Overrides that apply only to this interaction.

        Returns:
            The assembled model output.
        """
        # The awaitable boundary belongs to transport and credential reads.
        # Implementations delegate to the single interaction runtime.
        ...
