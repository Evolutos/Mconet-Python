"""Conformance contract for committed test-secret placeholders."""

import json
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_POLICY_PATH = (
    _PROJECT_ROOT / "spec" / "compatibility" / "test-secret-placeholders.json"
)
_EXPECTED_PLACEHOLDERS: dict[str, str] = {
    "api_key": "mconet-test-api-key-not-secret",
    "bearer_token": "mconet-test-bearer-token-not-secret",
    "signing_secret": "mconet-test-signing-secret-not-secret",
}
_EXPECTED_POLICY: dict[str, object] = {
    "environment": {
        "live_api_key": "MCONET_LIVE_API_KEY",
        "live_tests_enabled": "MCONET_RUN_LIVE_TESTS",
        "live_tests_enabled_value": "1",
    },
    "format_version": 1,
    "literal_rules": {
        "prefix": "mconet-test-",
        "suffix": "-not-secret",
    },
    "placeholders": _EXPECTED_PLACEHOLDERS,
    "profile": "test-secret-placeholders",
    "rules": {
        "committed_live_secret": "forbidden",
        "environment_default": "forbidden",
        "live_secret_logging": "forbidden",
        "live_secret_source": "environment-only",
        "placeholder_usage": ["documentation", "fixtures", "samples", "tests"],
    },
}


def test_secret_placeholder_policy_matches_frozen_contract() -> None:
    """Require the reviewed placeholder values and live-secret restrictions."""
    # Compare the complete document so changing a safe literal or weakening a
    # live-secret rule requires an explicit policy review.
    actual: object = json.loads(_POLICY_PATH.read_text(encoding="utf-8"))
    assert actual == _EXPECTED_POLICY


def test_placeholder_literals_are_visibly_non_secret() -> None:
    """Require every committed placeholder to follow the recognizable pattern."""
    # A common prefix and suffix keep fixtures easy to audit while ensuring no
    # placeholder resembles a provider-issued credential.
    assert all(
        value.startswith("mconet-test-") and value.endswith("-not-secret")
        for value in _EXPECTED_PLACEHOLDERS.values()
    )
