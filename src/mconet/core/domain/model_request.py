"""Open structural contract for one task-neutral model interaction request."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from mconet.core.domain.extensions import Extensions
from mconet.core.domain.model_target import ModelTarget
from mconet.core.domain.model_task_request import ModelTaskRequest
from mconet.core.domain.service_access import ServiceAccess


@runtime_checkable
class ModelRequest(Protocol):
    """Describe one model interaction without assuming a concrete task family.

    Implementations keep target selection, task input, optional per-request
    service access, descriptive metadata, and preserved extension fields as
    independent values. The structural contract permits application-defined
    request envelopes without SDK inheritance or registration.

    Interaction mode, runtime options, component injection, normalization,
    validation, protocol payloads, and transport state belong to later layers
    and are intentionally absent from this domain boundary.
    """

    @property
    def target(self) -> ModelTarget:
        """Return the service, protocol, deployment, and model selection."""
        # Keep routing identity separate from access configuration so credentials
        # and endpoints cannot become implicit properties of model selection.
        ...

    @property
    def task(self) -> ModelTaskRequest:
        """Return the open task request carried by this interaction envelope."""
        # Depend on the task-neutral protocol so conversation and future task
        # families cross the same outer request boundary without special fields.
        ...

    @property
    def service_access(self) -> ServiceAccess | None:
        """Return optional unresolved access input scoped to this request."""
        # None represents no request-level override; resolution may obtain access
        # from interaction options, client configuration, or integration defaults.
        ...

    @property
    def metadata(self) -> Extensions:
        """Return portable non-control metadata for the interaction request."""
        # Metadata remains descriptive and cannot silently configure task input,
        # routing, access, components, interaction mode, or transport behavior.
        ...

    @property
    def extensions(self) -> Extensions:
        """Return unknown request fields retained for forward compatibility."""
        # Preserve producer-owned JsonValue data without promoting unknown fields
        # into target, task, access, metadata, or runtime semantics.
        ...
