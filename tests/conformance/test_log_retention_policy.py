"""Conformance contract for test logging and retention governance."""

import json
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_POLICY_PATH = _PROJECT_ROOT / "spec" / "compatibility" / "test-log-policy.json"
_EXPECTED_POLICY: dict[str, object] = {
    "format_version": 1,
    "levels": {
        "debug": "local-opt-in",
        "default": "warning",
        "failure": "error",
        "live_test": "info",
    },
    "profile": "test-log-retention",
    "redaction": {
        "authorization": "always",
        "cookies": "always",
        "request_body": "disabled-by-default",
        "response_body": "disabled-by-default",
        "secret_values": "always",
        "url_userinfo": "always",
    },
    "responsibility": {
        "ci_owner": "configure-retention-and-access",
        "consumer": "do-not-emit-secrets",
        "emitting_component": "redact-before-emission",
        "test_harness": "scan-before-upload",
    },
    "retention": {
        "ci_job_logs_days": 14,
        "conformance_reports_days": 14,
        "live_test_reports_days": 7,
        "local_logs": "process-lifetime",
    },
    "upload": {
        "failed_test_logs": "sanitized-only",
        "raw_network_capture": "forbidden",
        "secret_scan_required": True,
    },
}


def test_log_retention_policy_matches_frozen_contract() -> None:
    """Require reviewed levels, retention periods, and ownership rules."""
    # Compare the complete document so weakening redaction or extending data
    # retention cannot occur as an incidental configuration edit.
    actual: object = json.loads(_POLICY_PATH.read_text(encoding="utf-8"))
    assert actual == _EXPECTED_POLICY
