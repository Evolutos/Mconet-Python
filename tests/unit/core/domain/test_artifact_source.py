"""Open descriptive contract tests for ArtifactSource implementations."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import cast

from mconet.core.domain import ArtifactSource, JsonValue, OpenIdentifier


@dataclass(frozen=True, slots=True)
class _Source:
    """Immutable source proving structural implementation without inheritance."""

    kind: OpenIdentifier
    """Standard or provider-defined source representation identity."""


@dataclass(frozen=True, slots=True)
class _ProviderObjectSource:
    """Describe provider object location data without implementing access."""

    kind: OpenIdentifier
    """Provider-defined source representation identity."""

    store_id: str
    """Opaque provider store identity retained as descriptive data."""

    object_key: str
    """Opaque provider object key retained without dereferencing it."""


def _serialize_source(source: ArtifactSource) -> dict[str, JsonValue]:
    """Serialize the common source contract into its portable public shape."""
    # Only the common classification crosses this abstraction boundary. Concrete
    # source serializers own their representation-specific descriptive fields.
    return {"kind": source.kind.value}


def _require_object(value: JsonValue, field_name: str) -> dict[str, JsonValue]:
    """Return one required object-valued decoded source document."""
    # Named fields prevent scalar and positional source forms from becoming
    # incompatible language-specific alternatives to the public contract.
    if not isinstance(value, dict):
        raise AssertionError(f"{field_name} must be a JSON object.")
    return value


def _require_string(value: JsonValue | None, field_name: str) -> str:
    """Return one required string-valued decoded source field."""
    # Source identity must remain exact text; null, booleans, numbers, arrays,
    # and objects are never coerced into an identifier by the test boundary.
    if not isinstance(value, str):
        raise AssertionError(f"{field_name} must be a JSON string.")
    return value


def _deserialize_source(document: dict[str, JsonValue]) -> _Source:
    """Reconstruct one source identity from its common portable shape."""
    # No registry lookup maps an unfamiliar source kind to a known fallback, so
    # future provider identifiers remain exact for a matching concrete decoder.
    return _Source(kind=OpenIdentifier(_require_string(document.get("kind"), "kind")))


def test_artifact_source_supports_structural_descriptions() -> None:
    """Verify common and provider-specific data can implement the protocol."""
    minimal = _Source(OpenIdentifier("vendor.inline_blob"))
    provider = _ProviderObjectSource(
        kind=OpenIdentifier("vendor.object_store"),
        store_id="store-primary",
        object_key="artifacts/item-1",
    )

    # Structural conformance requires no SDK inheritance. Additional concrete
    # fields remain descriptive and do not alter the common source identity.
    assert isinstance(minimal, ArtifactSource)
    assert isinstance(provider, ArtifactSource)
    assert minimal.kind.value == "vendor.inline_blob"
    assert provider.kind.value == "vendor.object_store"
    assert provider.store_id == "store-primary"
    assert provider.object_key == "artifacts/item-1"


def test_artifact_source_preserves_unknown_kind_through_json() -> None:
    """Verify an unknown source identity survives a portable JSON round trip."""
    source = _Source(OpenIdentifier("vendor.quantum_archive"))

    # Real encoding and decoding prove fidelity does not depend on comparing one
    # Python object or reusing its original OpenIdentifier instance.
    encoded = json.dumps(_serialize_source(source), sort_keys=True)
    decoded: JsonValue = json.loads(encoded)
    restored = _deserialize_source(_require_object(decoded, "source"))

    assert isinstance(restored, ArtifactSource)
    assert restored == source
    assert restored.kind is not source.kind
    assert restored.kind.value == "vendor.quantum_archive"


def test_artifact_source_protocol_declares_no_access_behavior() -> None:
    """Verify the common contract cannot read, open, fetch, or transfer content."""
    declared_properties = {
        name
        for name, value in vars(ArtifactSource).items()
        if isinstance(value, property)
    }
    declared_operations = {
        name
        for name, value in vars(ArtifactSource).items()
        if not name.startswith("_") and callable(value)
    }

    # Exact surface assertions prevent future convenience I/O methods from
    # silently coupling immutable source descriptions to side effects.
    assert declared_properties == {"kind"}
    assert declared_operations == set()


def test_artifact_source_requires_kind_identity() -> None:
    """Verify arbitrary location data cannot satisfy the source protocol."""

    @dataclass(frozen=True, slots=True)
    class _MissingKind:
        """Intentionally expose a locator without source classification."""

        locator: str
        """Location text that cannot substitute for an open kind identity."""

    candidate = _MissingKind("memory://artifact")

    # A locator shape and a bare OpenIdentifier are both incomplete because the
    # common protocol requires the named kind property on the source object.
    assert not isinstance(candidate, ArtifactSource)
    assert not isinstance(
        cast(object, OpenIdentifier("vendor.inline_blob")), ArtifactSource
    )
