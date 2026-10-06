"""Open structural contract for model task description data."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from mconet.core.domain.extensions import Extensions
from mconet.core.domain.open_identifier import OpenIdentifier


@runtime_checkable
class TaskDescriptor(Protocol):
    """Describe task identity, version, schemas, and portable auxiliary data.

    Implementations expose one stable read-only field surface without inheriting
    an SDK base class or registering task types. Semantic validation remains a
    separate concern so unknown task identifiers and future schema references can
    cross the common domain boundary without being interpreted by Core.
    """

    @property
    def type(self) -> OpenIdentifier:
        """Return the open identifier describing what task should be performed."""
        # Task identity stays independent from interaction mode, model protocol,
        # request transport, and any task-specific document node representation.
        ...

    @property
    def version(self) -> str | None:
        """Return the optional producer-declared task contract version."""
        # The protocol preserves version text as supplied; a dedicated validator
        # owns requiredness, syntax, compatibility, and supported-version policy.
        ...

    @property
    def input_schema_id(self) -> str | None:
        """Return the optional identifier of the task input schema."""
        # Input schema identity remains distinct from task type and output schema
        # so adapters cannot infer one contract dimension from another.
        ...

    @property
    def output_schema_id(self) -> str | None:
        """Return the optional identifier of the task output schema."""
        # Output schema identity is independently optional and cannot substitute
        # for validation of the actual result document produced by an adapter.
        ...

    @property
    def metadata(self) -> Extensions:
        """Return portable descriptive metadata associated with the task."""
        # Metadata carries non-control JsonValue facts only; execution settings,
        # credentials, and protocol request fields belong to separate contracts.
        ...

    @property
    def extensions(self) -> Extensions:
        """Return unknown versioned fields retained for forward compatibility."""
        # Extensions preserve producer-owned JsonValue data without promoting it
        # into standard schema, version, metadata, or execution semantics.
        ...
