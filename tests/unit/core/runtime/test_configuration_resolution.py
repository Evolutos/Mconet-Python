"""Tests that interaction configuration is not written back to the client."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

from mconet.core.domain import (
    CompatibilityPolicy,
    ConversationInputNode,
    ConversationTaskBuilder,
    Extensions,
    InteractionResourceLimits,
    MessageDocument,
    MessageElementKind,
    MessageEntry,
    MessageGroup,
    MessageRole,
    ModelDescriptor,
    ModelInteractionError,
    ModelRequest,
    ModelRequestBuilder,
    ModelTarget,
    NamedModel,
    OpenIdentifier,
    ResolvedInteractionResourceLimits,
    TaskDocument,
    TaskGroupNode,
    TaskNodeKind,
    TextMessageContent,
)
from mconet.core.runtime._configuration_resolution import (
    resolve_interaction_configuration,
)
from mconet.core.runtime.interaction_configuration_layer import (
    InteractionConfigurationLayer,
)


def _empty_extensions() -> Extensions:
    """Create independent empty extension storage for structural fixtures."""
    # Separate mappings keep one fixture from mutating another fixture's fields.
    return {}


def _noop_unsubscribe() -> None:
    """Return a completed remover for the passive cancellation fixture."""
    # The fixture keeps no subscriber, so removal has nothing to change.
    return None


def _capture(action: Callable[[], object]) -> BaseException:
    """Run one action and return the exception it raises."""
    try:
        action()
    except BaseException as error:
        return error
    raise AssertionError("Expected the action to fail.")


@dataclass(frozen=True, slots=True)
class _Target:
    """Structural model target stored on the request."""

    service_id: OpenIdentifier
    protocol_id: OpenIdentifier
    model: ModelDescriptor
    deployment_id: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _Mode:
    """Structural interaction mode."""

    id: OpenIdentifier


@dataclass(frozen=True, slots=True)
class _NodeKind:
    """Container kind for the task-document root."""

    id: OpenIdentifier
    composition: Literal["leaf", "container"] = "container"


@dataclass(frozen=True, slots=True)
class _MessageKind:
    """Container kind for the message-document root."""

    id: OpenIdentifier
    category: str
    composition: Literal["leaf", "container"]


@dataclass(frozen=True, slots=True)
class _Role:
    """Structural user role for the input message."""

    id: OpenIdentifier
    semantic: str | None = None
    raw_value: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


class _Signal:
    """Passive cancellation signal owned by one interaction."""

    @property
    def is_cancelled(self) -> bool:
        """Return the fixture's stable active state."""
        # Resolution must not cancel the signal while storing it.
        return False

    @property
    def reason(self) -> str | None:
        """Return no reason while the fixture stays active."""
        return None

    def subscribe(
        self,
        callback: Callable[[str | None], None],
    ) -> Callable[[], None]:
        """Return a completed remover without keeping the callback."""
        # Construction and resolution must not subscribe as a side effect.
        del callback
        return _noop_unsubscribe


def _request() -> ModelRequest:
    """Build one valid unary conversation request."""
    role: MessageRole = _Role(OpenIdentifier("message.user"))
    message_kind: MessageElementKind = _MessageKind(
        OpenIdentifier("message.root"),
        "group",
        "container",
    )
    entry = MessageEntry(
        "message-entry",
        role,
        (TextMessageContent("text-content", "Hello"),),
    )
    messages = MessageDocument(
        "1.0",
        "input",
        MessageGroup("message-root", message_kind, (entry,)),
    )
    kind: TaskNodeKind = _NodeKind(OpenIdentifier("task.root"))
    document = TaskDocument(
        "1.0",
        TaskGroupNode("root", kind, (ConversationInputNode("input", messages),)),
    )
    target: ModelTarget = _Target(
        OpenIdentifier("service.vendor"),
        OpenIdentifier("protocol.vendor"),
        NamedModel("vendor-model"),
    )
    return ModelRequestBuilder(
        target, ConversationTaskBuilder(document).build()
    ).build()


def test_interaction_overrides_do_not_write_back_to_the_client_layer() -> None:
    """Verify one-shot policy, limits, and cancellation stay off the client."""
    client_policy = CompatibilityPolicy(OpenIdentifier("compatible"))
    interaction_policy = CompatibilityPolicy(OpenIdentifier("strict"))
    client_limits = InteractionResourceLimits(80, None, None)
    interaction_limits = InteractionResourceLimits(50, None, None)
    signal = _Signal()
    client_layer = InteractionConfigurationLayer(
        compatibility_policy=client_policy,
        resource_limits=client_limits,
    )
    interaction_layer = InteractionConfigurationLayer(
        compatibility_policy=interaction_policy,
        resource_limits=interaction_limits,
        cancellation_signal=signal,
    )

    resolved = resolve_interaction_configuration(
        _request(),
        _Mode(OpenIdentifier("unary")),
        interaction_layer=interaction_layer,
        client_layer=client_layer,
        integration_layer=InteractionConfigurationLayer(),
        sdk_resource_limits=ResolvedInteractionResourceLimits(100, 200, 300),
    )

    # The result carries this interaction's values. The client layer still
    # holds the objects it had before the call.
    assert resolved.compatibility_policy is interaction_policy
    assert resolved.resource_limits.max_response_body_bytes == 50
    assert resolved.resource_limits.max_streaming_error_body_bytes == 200
    assert resolved.resource_limits.max_frame_bytes == 300
    assert resolved.cancellation_signal is signal
    assert client_layer.compatibility_policy is client_policy
    assert client_layer.resource_limits is client_limits
    assert client_layer.cancellation_signal is None


def test_failed_validation_does_not_change_the_client_layer() -> None:
    """Verify an unsupported mode leaves the client layer untouched."""
    client_policy = CompatibilityPolicy(OpenIdentifier("compatible"))
    client_layer = InteractionConfigurationLayer(compatibility_policy=client_policy)
    interaction_layer = InteractionConfigurationLayer(
        compatibility_policy=CompatibilityPolicy(OpenIdentifier("strict")),
        cancellation_signal=_Signal(),
    )

    error = _capture(
        lambda: resolve_interaction_configuration(
            _request(),
            _Mode(OpenIdentifier("server_stream")),
            interaction_layer=interaction_layer,
            client_layer=client_layer,
            integration_layer=InteractionConfigurationLayer(),
            sdk_resource_limits=ResolvedInteractionResourceLimits(100, 200, 300),
        )
    )

    assert isinstance(error, ModelInteractionError)
    assert error.code == "unsupported_interaction_mode"
    assert client_layer.compatibility_policy is client_policy
    assert client_layer.cancellation_signal is None
