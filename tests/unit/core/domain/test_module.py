"""Tests for the public core-domain module boundary."""

import mconet.core.domain


def test_core_domain_exports_only_completed_public_types() -> None:
    """Verify the domain root exposes only implemented public types."""
    # Keep exports explicit so incomplete types cannot enter the public API.
    assert mconet.core.domain.__all__ == (
        "Authorization",
        "AuthorizedSecretConsumer",
        "Bytes",
        "Diagnostic",
        "Duration",
        "ErrorCategory",
        "Extensions",
        "HeaderField",
        "Headers",
        "InteractionPhase",
        "JsonPrimitive",
        "JsonValue",
        "MediaType",
        "ModelDescriptor",
        "ModelInteractionError",
        "ModelTarget",
        "NamedModel",
        "OpenIdentifier",
        "OptionalField",
        "QueryParameter",
        "QueryParameters",
        "RecoveryHint",
        "SchemaVersion",
        "SecretValue",
        "ServiceAccess",
        "Timestamp",
        "UriValue",
        "parse_media_type",
        "parse_timestamp",
        "preserve_unknown_fields",
        "restore_preserved_fields",
        "serialize_optional_fields",
        "serialize_timestamp",
        "validate_duration",
        "validate_json_value_numbers",
        "validate_model_descriptor",
        "validate_model_target",
        "validate_open_identifier",
        "validate_uri",
    )
