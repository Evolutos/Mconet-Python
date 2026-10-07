"""Structural and responsibility tests for the message response mapper contract."""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Literal, get_type_hints

from mconet.core.domain import (
    ArtifactCatalog,
    MessageDocument,
    MessageGroup,
    OpenIdentifier,
)
from mconet.core.spi import (
    ComponentDescriptor,
    ErasedRuntimeValue,
    MessageMappingResult,
    MessageResponseMapper,
)


@dataclass(frozen=True, slots=True)
class _RootKind:
    """Provide the complete structural Kind for an output message root."""

    id: OpenIdentifier
    """Standard message-root identifier."""

    category: str
    """Grouping category retained by the mapped document."""

    composition: Literal["leaf", "container"]
    """Container composition required for a document root."""


class _Mapper:
    """Ordinary class implementing response mapping without SDK inheritance."""

    def __init__(
        self,
        descriptor: ComponentDescriptor,
        result: MessageMappingResult,
    ) -> None:
        """Store exact component metadata and the configured atomic result."""
        # The call record makes decoded-fragment identity observable, while the
        # prebuilt result isolates the protocol's composition responsibility.
        self.descriptor = descriptor
        self.result = result
        self.calls: list[ErasedRuntimeValue] = []

    def map_response(self, fragment: ErasedRuntimeValue) -> MessageMappingResult:
        """Record one decoded fragment and return the configured result pair."""
        # Returning the existing pair avoids decoding bytes, constructing a task
        # result, or publishing the document separately from its artifact scope.
        self.calls.append(fragment)
        return self.result


class _IncompleteMapper:
    """Component-shaped fixture intentionally missing response mapping."""

    descriptor = ComponentDescriptor("Incomplete", "1.0.0", "application")
    """Valid metadata isolates absence of the required behavior method."""


def _document() -> MessageDocument:
    """Build one valid output document for mapper contract tests."""
    # A complete domain value keeps the fixture on the production construction
    # path while an empty tree leaves tests focused on the response SPI boundary.
    root = MessageGroup(
        "root",
        _RootKind(OpenIdentifier("message.root"), "group", "container"),
        (),
    )
    return MessageDocument("1.0", "output", root)


def _mapping_result() -> MessageMappingResult:
    """Build one complete message-and-artifact result pair."""
    # An explicit empty catalog still proves that artifact scope is mandatory;
    # response mapping never represents completion with a document alone.
    return MessageMappingResult(_document(), ArtifactCatalog())


def _accept_mapper(mapper: MessageResponseMapper) -> MessageResponseMapper:
    """Return a mapper after crossing the statically checked protocol boundary."""
    # Pyright verifies the ordinary implementation's metadata and mapping
    # signatures without an SDK base class, explicit registration, or a cast.
    return mapper


def test_message_response_mapper_accepts_ordinary_structural_class() -> None:
    """Require only component metadata and the documented mapping operation."""
    mapper = _Mapper(
        ComponentDescriptor("Fixture mapper", "1.0.0", "application"),
        _mapping_result(),
    )

    accepted = _accept_mapper(mapper)

    # Static and runtime conformance agree without inheritance, a component ID,
    # lifecycle methods, or protocol-specific DTOs in the public contract.
    assert accepted is mapper
    assert isinstance(mapper, MessageResponseMapper)
    assert mapper.descriptor.name == "Fixture mapper"


def test_message_response_mapper_preserves_atomic_result_identity() -> None:
    """Pass through the decoded fragment and exact document/catalog pair."""
    native_fragment = {"role": "assistant", "content": "hello"}
    fragment = ErasedRuntimeValue(
        OpenIdentifier("protocol.message"),
        native_fragment,
        "message.v1",
    )
    expected = _mapping_result()
    mapper = _Mapper(
        ComponentDescriptor("Fixture mapper", "1.0.0", "application"),
        expected,
    )

    result = mapper.map_response(fragment)

    # Identity checks prove the mapper receives already-decoded native data and
    # returns one intact pair rather than publishing either member independently.
    assert mapper.calls == [fragment]
    assert mapper.calls[0] is fragment
    assert fragment.value is native_fragment
    assert result is expected
    assert result.document is expected.document
    assert result.artifacts is expected.artifacts


def test_message_response_mapper_has_exact_synchronous_method_surface() -> None:
    """Lock the method name, argument order, and synchronous mapping semantics."""
    method = MessageResponseMapper.map_response
    annotations = get_type_hints(method)

    # The narrow signature prevents bytes, transport metadata, authorization,
    # task results, or artifact registries from entering message-only mapping.
    assert tuple(inspect.signature(method).parameters) == ("self", "fragment")
    assert annotations == {
        "fragment": ErasedRuntimeValue,
        "return": MessageMappingResult,
    }
    assert not inspect.iscoroutinefunction(method)


def test_message_response_mapper_requires_complete_behavior_surface() -> None:
    """Reject component metadata when the mapping operation is absent."""
    incomplete = _IncompleteMapper()

    # Descriptor conformance alone cannot make a component usable as a mapper;
    # runtime structural recognition also requires the exact behavior member.
    assert not isinstance(incomplete, MessageResponseMapper)


def test_message_response_mapper_excludes_other_pipeline_responsibilities() -> None:
    """Keep decoding, transport, task assembly, and catalog merging out of the SPI."""
    mapper = _Mapper(
        ComponentDescriptor("Fixture mapper", "1.0.0", "application"),
        _mapping_result(),
    )

    # The contract exposes one mapping operation only. These negative assertions
    # guard against silently merging adjacent pipeline stages into the mapper.
    for forbidden_member in (
        "decode",
        "authorize",
        "send",
        "parse_response",
        "build_task_result",
        "merge_artifacts",
        "register",
    ):
        assert not hasattr(mapper, forbidden_member)
