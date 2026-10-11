"""Resolution tests for the JSON payload encoder capability."""

from dataclasses import dataclass, field

from mconet.codec.json import (
    JSON_PAYLOAD_ENCODER_CAPABILITY,
    JsonPayloadEncoder,
)
from mconet.core.domain import Extensions, ModelInteractionError, OpenIdentifier
from mconet.core.runtime._capability_resolution import resolve_capabilities
from mconet.core.spi import (
    CapabilityRequirement,
    ComponentRole,
    ComponentSelectionResolution,
    SelectedComponent,
)


def _empty_extensions() -> Extensions:
    """Return a fresh empty constraint map for one requirement."""
    return {}


@dataclass(frozen=True, slots=True)
class _Requirement:
    """Minimal capability requirement used only by this resolution fixture."""

    capability_id: OpenIdentifier
    """Open capability id requested by the interaction."""

    required: bool = True
    """Whether a missing provider must fail resolution."""

    constraints: Extensions = field(default_factory=_empty_extensions)
    """Empty constraints so an ID-only descriptor declaration can match."""

    source_path: str | None = "task.capabilities.codec.json.encode"
    """Diagnostic origin retained on the satisfied requirement."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Unknown requirement facts that do not affect identity matching."""


def _selected(encoder: JsonPayloadEncoder) -> SelectedComponent:
    """Snapshot the encoder under the request-encoder role."""
    return SelectedComponent(
        ComponentRole(OpenIdentifier("codec.request.encoder")),
        encoder,
        encoder.descriptor,
    )


def test_json_payload_encoder_capability_resolves_from_descriptor() -> None:
    """Verify codec.json.encode is satisfied by the selected encoder."""
    encoder = JsonPayloadEncoder()
    requirement = _Requirement(JSON_PAYLOAD_ENCODER_CAPABILITY)
    assert isinstance(requirement, CapabilityRequirement)

    result = resolve_capabilities(
        (requirement,),
        ComponentSelectionResolution((_selected(encoder),)),
    )

    # Resolution uses the capability id, not the diagnostic component name.
    assert JSON_PAYLOAD_ENCODER_CAPABILITY == OpenIdentifier("codec.json.encode")
    assert encoder.descriptor.name != JSON_PAYLOAD_ENCODER_CAPABILITY.value
    assert len(result.satisfied) == 1
    assert result.satisfied[0].requirement is requirement
    assert result.satisfied[0].capability.id == JSON_PAYLOAD_ENCODER_CAPABILITY
    assert result.satisfied[0].provider_id == "codec.request.encoder"
    assert result.optional_unsupported == ()


def test_json_payload_encoder_capability_does_not_satisfy_other_ids() -> None:
    """Verify an unrelated required capability stays unsupported."""
    encoder = JsonPayloadEncoder()
    requirement = _Requirement(OpenIdentifier("codec.json.decode"))

    try:
        resolve_capabilities(
            (requirement,),
            ComponentSelectionResolution((_selected(encoder),)),
        )
    except ModelInteractionError as error:
        # The stable code identifies the miss without quoting the requested id.
        assert error.code == "unsupported_capability"
        assert "codec.json.decode" not in error.message
        return
    raise AssertionError("Expected ModelInteractionError to be raised.")
