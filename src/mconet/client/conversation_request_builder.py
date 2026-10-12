"""Fluent construction of one conversation model request."""

from __future__ import annotations

from typing import Self, cast

from mconet.core.domain.conversation_task_request import ConversationTaskRequest
from mconet.core.domain.extensions import Extensions
from mconet.core.domain.model_request import ModelRequest
from mconet.core.domain.model_request_builder import ModelRequestBuilder
from mconet.core.domain.model_target import ModelTarget
from mconet.core.domain.service_access import ServiceAccess


class ConversationRequestBuilder:
    """Build one conversation model request from domain values only.

    The target and conversation task are required. Service access, metadata,
    and extensions are optional and are stored by the existing model-request
    builder. :meth:`build` returns that builder's validated request. This type
    does not plan, encode, authorize, or send.

    The builder is mutable and is not shared across requests. Each
    :meth:`build` call returns a new immutable request.
    """

    __slots__ = ("_builder",)

    def __init__(self, target: ModelTarget, task: ConversationTaskRequest) -> None:
        """Start a builder for one conversation task.

        Args:
            target: Routing target retained by identity.
            task: Conversation task retained by identity.

        Raises:
            TypeError: If ``target`` is not a model target or ``task`` is not
                a conversation task request.
        """
        candidate_target = cast(object, target)
        candidate_task = cast(object, task)
        if not isinstance(candidate_target, ModelTarget):
            raise TypeError(
                "ConversationRequestBuilder target must implement ModelTarget."
            )
        # A different task family stays on ModelRequestBuilder. This builder
        # only accepts the conversation task it can name.
        if not isinstance(candidate_task, ConversationTaskRequest):
            raise TypeError(
                "ConversationRequestBuilder task must be a ConversationTaskRequest."
            )
        self._builder = ModelRequestBuilder(candidate_target, candidate_task)

    def with_service_access(self, service_access: ServiceAccess | None) -> Self:
        """Replace or clear the request-level service access.

        Args:
            service_access: Unresolved access input, or None.

        Returns:
            This builder.

        Raises:
            TypeError: If a present value does not implement service access.
        """
        self._builder.with_service_access(service_access)
        return self

    def with_metadata(self, metadata: Extensions) -> Self:
        """Replace request metadata.

        Args:
            metadata: String-keyed descriptive JSON values.

        Returns:
            This builder.

        Raises:
            TypeError: If ``metadata`` is not a string-keyed mapping.
        """
        self._builder.with_metadata(metadata)
        return self

    def with_extensions(self, extensions: Extensions) -> Self:
        """Replace unknown request fields.

        Args:
            extensions: String-keyed forward-compatible JSON values.

        Returns:
            This builder.

        Raises:
            TypeError: If ``extensions`` is not a string-keyed mapping.
        """
        self._builder.with_extensions(extensions)
        return self

    def build(self) -> ModelRequest:
        """Return one validated model request for the stored conversation task.

        Returns:
            The immutable request produced by the domain model-request builder.

        Raises:
            TypeError: If a stored field has an invalid shape.
            ValueError: If target, task, access, or JSON semantics are invalid.
            ModelInteractionError: If the conversation task exceeds its scope.
        """
        # Validation and object creation stay in the domain builder. No
        # protocol component is selected or called from this method.
        return self._builder.build()
