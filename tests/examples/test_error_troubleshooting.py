"""Standard error categories, phases, and codes are searchable."""

from __future__ import annotations

from pathlib import Path

_GUIDE = Path(__file__).parents[2] / "docs" / "error-troubleshooting.md"

_CATEGORIES = (
    "invalid_request",
    "invalid_component_configuration",
    "unsupported_feature",
    "authentication",
    "permission",
    "rate_limit",
    "content_filter",
    "context_length",
    "timeout",
    "cancelled",
    "network",
    "serialization",
    "deserialization",
    "protocol",
    "model_service",
    "unknown",
)
_PHASES = (
    "normalization",
    "validation",
    "component_resolution",
    "model_integration_resolution",
    "protocol_planning",
    "capability_resolution",
    "component_type_validation",
    "artifact_resolution",
    "protocol_adaptation",
    "encoding",
    "authentication",
    "transport",
    "stream_framing",
    "stream_mapping",
    "duplex_session",
    "long_running_operation",
    "decoding",
    "response_parsing",
    "monitoring",
)
_CODES = (
    "unsupported_model_integration",
    "ambiguous_model_integration",
    "invalid_model_descriptor",
    "invalid_integration_binding",
    "unsupported_task",
    "unsupported_interaction_mode",
    "unsupported_capability",
    "ambiguous_capability_provider",
    "invalid_component_type_contract",
    "component_type_mismatch",
    "component_not_found",
    "ambiguous_component_selection",
    "unsupported_artifact_source",
    "artifact_reference_not_found",
    "duplicate_artifact_id",
    "artifact_access_failed",
    "artifact_transfer_failed",
    "unsupported_body_signing",
    "body_not_replayable",
    "body_already_consumed",
    "response_body_too_large",
    "stream_frame_too_large",
    "stream_events_consumed",
    "client_closed",
    "invalid_monitoring_merge_mode",
)


def test_error_guide_lists_standard_categories_phases_and_codes() -> None:
    """Verify each standard diagnostic token can be found in the guide."""
    text = _GUIDE.read_text(encoding="utf-8")
    for token in (*_CATEGORIES, *_PHASES, *_CODES):
        assert f"`{token}`" in text
