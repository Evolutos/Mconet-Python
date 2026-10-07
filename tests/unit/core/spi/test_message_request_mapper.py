"""Structural and responsibility tests for the message request mapper contract."""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Literal, get_type_hints

from mconet.core.domain import MessageDocument, MessageGroup, OpenIdentifier
from mconet.core.spi import (
    ComponentDescriptor,
    ErasedRuntimeValue,
    MessageRequestMapper,
)


@dataclass(frozen=True, slots=True)
class _RootKind:
    """Provide the complete structural Kind for an input message root."""

    id: OpenIdentifier
    """Standard message-root identifier."""

    category: str
    """Grouping category retained by the document."""

    composition: Literal["leaf", "container"]
    """Container composition required for a document root."""


class _Mapper:
    """Ordinary class implementing message mapping without SDK inheritance."""

    def __init__(
        self,
        descriptor: ComponentDescriptor,
        fragment: ErasedRuntimeValue,
    ) -> None:
        """Store the exact configured metadata and native mapping result."""
        # The call record exposes whether mapping received the complete document
        # unchanged, while the configured fragment isolates contract behavior.
        self.descriptor = descriptor
        self.fragment = fragment
        self.calls: list[MessageDocument] = []

    def map_request(self, document: MessageDocument) -> ErasedRuntimeValue:
        """Record one document and return the configured protocol fragment."""
        # No serialization or request mutation occurs: the task adapter will
        # compose this native fragment before a dedicated Codec produces bytes.
        self.calls.append(document)
        return self.fragment


class _IncompleteMapper:
    """Component-shaped fixture intentionally missing request mapping."""

    descriptor = ComponentDescriptor("Incomplete", "1.0.0", "application")
    """Valid metadata isolates absence of the required behavior method."""


def _document() -> MessageDocument:
    """Build one valid input document for mapper contract tests."""
    # A complete public domain value verifies the mapper consumes the document
    # boundary rather than a bare root group or protocol-specific message list.
    root = MessageGroup(
        "root",
        _RootKind(OpenIdentifier("message.root"), "group", "container"),
        (),
    )
    return MessageDocument("1.0", "input", root)


def _accept_mapper(mapper: MessageRequestMapper) -> MessageRequestMapper:
    """Return a mapper after crossing the statically checked protocol boundary."""
    # Pyright verifies the ordinary implementation's metadata and mapping
    # signatures without an SDK base class, explicit registration, or a cast.
    return mapper


def test_message_request_mapper_accepts_ordinary_structural_class() -> None:
    """Require only component metadata and the documented mapping operation."""
    fragment = ErasedRuntimeValue(OpenIdentifier("protocol.messages"), [])
    mapper = _Mapper(
        ComponentDescriptor("Fixture mapper", "1.0.0", "application"),
        fragment,
    )

    accepted = _accept_mapper(mapper)

    # Static and runtime conformance agree without inheritance, a component ID,
    # lifecycle methods, or protocol-specific types in the public contract.
    assert accepted is mapper
    assert isinstance(mapper, MessageRequestMapper)
    assert mapper.descriptor.name == "Fixture mapper"


def test_message_request_mapper_preserves_input_and_native_output_identity() -> None:
    """Pass the exact document through and retain the mapper-owned fragment."""
    document = _document()
    fragment_value: list[dict[str, str]] = [{"role": "user", "content": "hello"}]
    fragment = ErasedRuntimeValue(
        OpenIdentifier("protocol.messages"),
        fragment_value,
        "messages.v1",
    )
    mapper = _Mapper(
        ComponentDescriptor("Fixture mapper", "1.0.0", "application"),
        fragment,
    )

    result = mapper.map_request(document)

    # Identity checks prove the protocol neither copies the domain document nor
    # serializes, normalizes, or reconstructs the native protocol representation.
    assert mapper.calls == [document]
    assert mapper.calls[0] is document
    assert result is fragment
    assert result.value is fragment_value


def test_message_request_mapper_has_exact_synchronous_method_surface() -> None:
    """Lock the method name, argument order, and synchronous mapping semantics."""
    method = MessageRequestMapper.map_request
    annotations = get_type_hints(method)

    # The narrow signature prevents task options, bytes, authorization state,
    # transport objects, or registries from leaking into message-only mapping.
    assert tuple(inspect.signature(method).parameters) == ("self", "document")
    assert annotations == {
        "document": MessageDocument,
        "return": ErasedRuntimeValue,
    }
    assert not inspect.iscoroutinefunction(method)


def test_message_request_mapper_requires_complete_behavior_surface() -> None:
    """Reject component metadata when the mapping operation is absent."""
    incomplete = _IncompleteMapper()

    # Descriptor conformance alone cannot make a component usable as a mapper;
    # runtime structural recognition also requires the exact behavior member.
    assert not isinstance(incomplete, MessageRequestMapper)


def test_message_request_mapper_excludes_other_pipeline_responsibilities() -> None:
    """Keep encoding, authorization, transport, and task mapping out of the SPI."""
    fragment = ErasedRuntimeValue(OpenIdentifier("protocol.messages"), ())
    mapper = _Mapper(
        ComponentDescriptor("Fixture mapper", "1.0.0", "application"),
        fragment,
    )

    # The contract exposes one mapping operation only. These negative assertions
    # guard against silently merging adjacent pipeline components into the mapper.
    for forbidden_member in (
        "encode",
        "authorize",
        "send",
        "prepare_plan",
        "build_request",
        "register",
    ):
        assert not hasattr(mapper, forbidden_member)
