"""Structural boundary tests for the open ModelTarget protocol."""

from dataclasses import dataclass, field

from mconet.core.domain import (
    Extensions,
    ModelDescriptor,
    ModelTarget,
    NamedModel,
    OpenIdentifier,
)


def _empty_extensions() -> Extensions:
    """Create a typed empty target extension mapping for test defaults."""
    return {}


@dataclass(frozen=True, slots=True)
class _CustomTarget:
    """Custom target proving the protocol needs no SDK concrete base type."""

    service_id: OpenIdentifier
    protocol_id: OpenIdentifier
    model: ModelDescriptor
    deployment_id: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


def test_model_target_keeps_target_dimensions_separate() -> None:
    """Verify service, protocol, model, and deployment remain independent."""
    target = _CustomTarget(
        service_id=OpenIdentifier("service.dashscope"),
        protocol_id=OpenIdentifier("protocol.openai_compatible"),
        model=NamedModel("qwen-plus"),
        deployment_id="production-a",
        extensions={"futureRoutingHint": "region-a"},
    )

    # Structural recognition preserves the custom target while every selection
    # dimension and unknown extension remains independently observable.
    assert isinstance(target, ModelTarget)
    assert target.service_id == OpenIdentifier("service.dashscope")
    assert target.protocol_id == OpenIdentifier("protocol.openai_compatible")
    assert target.model.name == "qwen-plus"
    assert target.deployment_id == "production-a"
    assert target.extensions == {"futureRoutingHint": "region-a"}


def test_model_target_requires_the_complete_target_surface() -> None:
    """Verify service and model alone cannot satisfy the target contract."""

    @dataclass(frozen=True, slots=True)
    class _IncompleteTarget:
        """Intentionally omit protocol, deployment, and extension properties."""

        service_id: OpenIdentifier
        model: ModelDescriptor

    # Optional deployment values may be None, but the property itself and every
    # other target dimension must remain present on all implementations.
    incomplete = _IncompleteTarget(OpenIdentifier("service.local"), NamedModel("m"))
    assert not isinstance(incomplete, ModelTarget)
