"""Internal exact lookup key for the model integration type table."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from mconet.core.domain import (
    InteractionMode,
    ModelTarget,
    OpenIdentifier,
    TaskDescriptor,
    validate_open_identifier,
)

# The open identifier grammar admits only lowercase ASCII letters, digits, "_",
# "-", and ".", so "/" can never occur inside a part and the joined text is
# reversible without escaping.
_SEPARATOR = "/"


@dataclass(frozen=True, slots=True)
class IntegrationTypeKey:
    """Name one protocol, task type, and interaction mode combination.

    The three parts stay separate fields so no part can be confused with
    another. The key deliberately has no service, model name, family, or
    deployment: one protocol serves many services and models, and resolving an
    integration from a model name would be a guess.
    """

    protocol_id: OpenIdentifier
    """Wire protocol the target names."""

    task_type: OpenIdentifier
    """Task type of the request's TaskDescriptor."""

    mode_id: OpenIdentifier
    """Identifier of the requested InteractionMode."""

    def __post_init__(self) -> None:
        """Require three valid open identifiers so serialization is injective."""
        for field_name in ("protocol_id", "task_type", "mode_id"):
            value = cast(object, getattr(self, field_name))
            if not isinstance(value, OpenIdentifier):
                raise TypeError(
                    f"IntegrationTypeKey {field_name} must be an OpenIdentifier."
                )
            # Grammar validation is what keeps the separator out of every part.
            validate_open_identifier(value)

    @classmethod
    def for_request(
        cls,
        target: ModelTarget,
        task: TaskDescriptor,
        mode: InteractionMode,
    ) -> IntegrationTypeKey:
        """Return the key of one resolution request.

        Args:
            target: Model target being resolved. Only ``protocol_id`` is read.
            task: Task descriptor. Only ``type`` is read.
            mode: Interaction mode. Only ``id`` is read.

        Returns:
            The key that an exact type table entry must equal.
        """
        return cls(target.protocol_id, task.type, mode.id)

    def serialize(self) -> str:
        """Return the canonical text form shared by every SDK language.

        The form is ``protocol/task/mode`` using the exact identifier text,
        with no normalization. Equal keys always produce equal text and
        different keys always produce different text.

        Returns:
            The canonical serialized key.
        """
        return _SEPARATOR.join(
            (self.protocol_id.value, self.task_type.value, self.mode_id.value)
        )
