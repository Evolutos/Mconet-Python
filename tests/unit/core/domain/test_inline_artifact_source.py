"""Tests for immutable inline artifact byte sources."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import FrozenInstanceError
from typing import cast

from mconet.core.domain import (
    ArtifactSource,
    Bytes,
    InlineArtifactSource,
    OpenIdentifier,
)


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    # A narrow exception boundary ensures unrelated fixture failures cannot make
    # a storage or immutability assertion pass accidentally.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_inline_artifact_source_preserves_immutable_bytes() -> None:
    """Verify inline content is retained exactly as a read-only byte value."""
    content = Bytes(bytes((0, 127, 255)))
    source = InlineArtifactSource(content)

    # The source does not copy or transform already immutable content, preserving
    # exact octets and the zero-copy value semantics of the Bytes foundation type.
    assert source.bytes is content
    assert source.bytes == b"\x00\x7f\xff"
    assert type(source.bytes) is bytes
    assert not hasattr(source.bytes, "__setitem__")


def test_inline_artifact_source_supports_empty_content() -> None:
    """Verify an empty byte payload remains a valid explicit inline source."""
    source = InlineArtifactSource(Bytes(b""))

    # Payload length is a content concern; representing zero bytes does not mean
    # the source is absent and therefore needs no alternate null state.
    assert source.bytes == b""


def test_inline_artifact_source_has_standard_source_identity() -> None:
    """Verify the concrete value satisfies ArtifactSource with a stable kind."""
    first = InlineArtifactSource(Bytes(b"first"))
    second = InlineArtifactSource(Bytes(b"second"))

    # Classification depends on the source representation, never payload content.
    # The identifier stays open and can be matched by future requirements.
    assert isinstance(first, ArtifactSource)
    assert first.kind == OpenIdentifier("artifact.inline")
    assert second.kind == first.kind
    assert first.kind is second.kind


def test_inline_artifact_source_is_frozen_and_data_only() -> None:
    """Verify the source exposes one data input and no I/O operations."""
    source = InlineArtifactSource(Bytes(b"content"))
    parameters = tuple(inspect.signature(InlineArtifactSource).parameters)

    # The single constructor parameter keeps access behavior out of the value.
    # Explicit absence checks guard against later convenience methods introducing
    # hidden reads, stream creation, network access, or transfer side effects.
    assert parameters == ("bytes",)
    assert not hasattr(source, "read")
    assert not hasattr(source, "open")
    assert not hasattr(source, "stream")
    assert not hasattr(source, "upload")
    _assert_raises(
        FrozenInstanceError,
        lambda: source.__setattr__("bytes", Bytes(b"replacement")),
        "cannot assign to field",
    )


def test_inline_artifact_source_rejects_non_bytes_values() -> None:
    """Verify dynamic callers cannot retain mutable or unrelated payloads."""
    # Static typing rejects these inputs before runtime. The explicit checks keep
    # the same invariant when untyped integrations bypass the type checker.
    for value in (bytearray(b"mutable"), memoryview(b"view"), "text", None):
        _assert_raises(
            TypeError,
            lambda value=value: InlineArtifactSource(cast(Bytes, value)),
            "bytes must be a Bytes value",
        )
