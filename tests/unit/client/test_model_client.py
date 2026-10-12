"""Reusable ModelClient interactor and close contract."""

from __future__ import annotations

import asyncio
import inspect
from typing import cast

from mconet.client.model_client import ModelClient
from mconet.core.domain import ModelInteractionError, ModelRequest
from mconet.core.spi import (
    ComponentDescriptor,
    InteractionOptions,
    ModelClientConfiguration,
    ModelInteractor,
    PayloadEncoder,
    RuntimeComponents,
    Transport,
)


class _Encoder:
    """Reusable encoder stored on a client configuration."""

    def __init__(self) -> None:
        """Store metadata and an invocation counter."""
        self.descriptor = ComponentDescriptor("encoder", "1.0.0", "application")
        self.calls: list[str] = []

    def encode(self, payload: object) -> object:
        """Record an encode call that client construction must not make."""
        del payload
        self.calls.append("encode")
        return None


class _Metadata:
    """Descriptor-only object that does not implement a behavior protocol."""

    def __init__(self) -> None:
        """Store metadata without behavior methods."""
        self.descriptor = ComponentDescriptor("metadata", "1.0.0", "application")


class _Resource:
    """Closeable resource that client close must not release."""

    def __init__(self) -> None:
        """Store metadata and a close counter."""
        self.descriptor = ComponentDescriptor("transport", "1.0.0", "application")
        self.calls: list[str] = []

    async def close(self) -> None:
        """Record a close call that the client contract must not make."""
        self.calls.append("close")

    async def send(self, *values: object) -> object:
        """Record a send call that client construction must not make."""
        del values
        self.calls.append("send")
        return None


class _Framer:
    """Per-interaction state that cannot be stored on the client."""

    def __init__(self) -> None:
        """Store metadata and an invocation counter."""
        self.descriptor = ComponentDescriptor("framer", "1.0.0", "application")
        self.calls: list[str] = []

    def frame(self, data: object) -> object:
        """Record a frame call that client construction must not make."""
        del data
        self.calls.append("frame")
        return None

    async def send(self, *values: object) -> object:
        """Satisfy transport presence without running during construction."""
        del values
        self.calls.append("send")
        return None


def test_client_unifies_interactor_and_close_without_interaction_state() -> None:
    """Verify one reusable object is the interactor and the close entry."""
    configuration = ModelClientConfiguration()
    client = ModelClient(configuration)
    other = ModelClient(configuration)
    assert client.configuration is configuration
    assert other.configuration is configuration
    assert isinstance(client, ModelInteractor)
    assert inspect.iscoroutinefunction(ModelClient.interact)
    assert inspect.iscoroutinefunction(ModelClient.close)
    assert ModelClient.__slots__ == ("_configuration",)
    for name in ("stream", "send_stream", "open_session", "submit"):
        assert not hasattr(client, name)


def test_close_does_not_release_an_injected_resource() -> None:
    """Verify close stays on the client and leaves an injected transport open."""
    resource = _Resource()
    configuration = ModelClientConfiguration(
        components=RuntimeComponents(transport=cast(Transport, resource))
    )
    client = ModelClient(configuration)
    asyncio.run(client.close())
    asyncio.run(client.close())
    assert resource.calls == []
    assert client.configuration is configuration


def test_injected_components_fail_during_construction() -> None:
    """Verify an illegal injected component aborts client construction."""
    metadata = RuntimeComponents(payload_encoder=cast(PayloadEncoder, _Metadata()))
    try:
        ModelClient(ModelClientConfiguration(components=metadata))
    except TypeError as error:
        assert "declared behavior protocol" in str(error)
    else:
        raise AssertionError("Expected a descriptor-only encoder to be rejected.")

    framer = RuntimeComponents(transport=cast(Transport, _Framer()))
    try:
        ModelClient(ModelClientConfiguration(components=framer))
    except ModelInteractionError as error:
        assert error.code == "invalid_component_lifecycle"
    else:
        raise AssertionError("Expected a stateful instance to be rejected.")


def test_valid_injection_is_retained_without_calling_behavior() -> None:
    """Verify a legal encoder stays on the shared configuration and stays idle."""
    encoder = _Encoder()
    components = RuntimeComponents(payload_encoder=cast(PayloadEncoder, encoder))
    configuration = ModelClientConfiguration(components=components)
    client = ModelClient(configuration)
    assert client.configuration.components is components
    assert encoder.calls == []


def test_interact_checks_arguments_and_does_not_store_the_request() -> None:
    """Verify interact belongs to the client but does not execute a pipeline."""
    client = ModelClient(ModelClientConfiguration())
    try:
        asyncio.run(
            client.interact(
                cast(ModelRequest, object()),
                InteractionOptions(),
            )
        )
    except TypeError as error:
        assert "request must be a ModelRequest" in str(error)
    else:
        raise AssertionError("Expected a non-request to be rejected.")
    assert client.configuration.components is None
