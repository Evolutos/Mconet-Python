"""Open structural contract for one model interaction target."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from mconet.core.domain.extensions import Extensions
from mconet.core.domain.model_descriptor import ModelDescriptor
from mconet.core.domain.open_identifier import OpenIdentifier


@runtime_checkable
class ModelTarget(Protocol):
    """Identify a service, protocol, model, and optional deployment separately.

    The target contains no endpoint, authorization, transport, or credential
    data. Implementations remain structural so integrations can add concrete
    target types without registration or inheritance from an SDK base class.
    """

    @property
    def service_id(self) -> OpenIdentifier:
        """Return the model service identifier."""
        ...

    @property
    def protocol_id(self) -> OpenIdentifier:
        """Return the interaction protocol identifier."""
        ...

    @property
    def model(self) -> ModelDescriptor:
        """Return the model descriptor selected for the interaction."""
        ...

    @property
    def deployment_id(self) -> str | None:
        """Return an optional service-side deployment identifier."""
        ...

    @property
    def extensions(self) -> Extensions:
        """Return unknown versioned target fields for forward compatibility."""
        ...
