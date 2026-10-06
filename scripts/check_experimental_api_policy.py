"""Validate the frozen experimental API lifecycle policy."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import cast

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_POLICY_PATH = _PROJECT_ROOT / "spec" / "compatibility" / "experimental-api-policy.json"
_EXPECTED_EVIDENCE = {
    "addition": frozenset(
        {
            "documented_use_case",
            "introduced_version",
            "named_owner",
            "public_documentation",
            "tests",
            "tracking_issue",
        }
    ),
    "promotion": frozenset(
        {
            "adoption_evidence",
            "api_review",
            "contract_tests",
            "migration_notes",
            "no_open_blockers",
        }
    ),
    "removal": frozenset({"deprecation_notice", "migration_path", "release_notes"}),
}


class ExperimentalApiPolicyValidationError(ValueError):
    """Report an incomplete or changed experimental API policy."""


def _require_exact_keys(
    document: Mapping[str, object], expected: frozenset[str], location: str
) -> None:
    """Reject missing or undocumented lifecycle fields."""
    actual = frozenset(document)
    if actual != expected:
        missing = sorted(expected - actual)
        unexpected = sorted(actual - expected)
        raise ExperimentalApiPolicyValidationError(
            f"Invalid fields in {location}: missing={missing}, unexpected={unexpected}."
        )


def _require_mapping(value: object, location: str) -> dict[str, object]:
    """Return a string-keyed object from the untyped JSON boundary."""
    if not isinstance(value, dict):
        raise ExperimentalApiPolicyValidationError(f"Expected an object at {location}.")

    mapping: dict[str, object] = {}
    for key, item in cast(dict[object, object], value).items():
        if not isinstance(key, str):
            raise ExperimentalApiPolicyValidationError(
                f"Expected only string keys at {location}."
            )
        mapping[key] = item
    return mapping


def _load_policy() -> dict[str, object]:
    """Load the experimental API policy as a validated root object."""
    try:
        raw_document: object = json.loads(_POLICY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ExperimentalApiPolicyValidationError(
            f"Cannot read valid JSON from {_POLICY_PATH}: {error}"
        ) from error
    return _require_mapping(raw_document, str(_POLICY_PATH))


def _validate_evidence(value: object, lifecycle: str) -> None:
    """Require a sorted, unique, and complete lifecycle evidence list."""
    if not isinstance(value, list):
        raise ExperimentalApiPolicyValidationError(
            f"{lifecycle}.required_evidence must be a list."
        )

    evidence: list[str] = []
    for item in cast(list[object], value):
        if not isinstance(item, str) or not item:
            raise ExperimentalApiPolicyValidationError(
                f"{lifecycle}.required_evidence must contain non-empty strings."
            )
        evidence.append(item)
    if evidence != sorted(set(evidence)):
        raise ExperimentalApiPolicyValidationError(
            f"{lifecycle}.required_evidence must be sorted and unique."
        )
    if frozenset(evidence) != _EXPECTED_EVIDENCE[lifecycle]:
        raise ExperimentalApiPolicyValidationError(
            f"{lifecycle}.required_evidence has drifted."
        )


def _validate_policy() -> None:
    """Validate designation, addition, promotion, and removal rules."""
    document = _load_policy()
    _require_exact_keys(
        document,
        frozenset(
            {
                "addition",
                "designation",
                "format_version",
                "platform",
                "promotion",
                "removal",
            }
        ),
        str(_POLICY_PATH),
    )
    if document["format_version"] != 1:
        raise ExperimentalApiPolicyValidationError("format_version must be 1.")
    if document["platform"] != "python":
        raise ExperimentalApiPolicyValidationError("platform must be python.")

    designation = _require_mapping(document["designation"], "designation")
    expected_designation: dict[str, object] = {
        "documentation_label": "Experimental",
        "metadata_attribute": "__mconet_stability__",
        "metadata_value": "experimental",
    }
    if designation != expected_designation:
        raise ExperimentalApiPolicyValidationError("designation has drifted.")

    addition = _require_mapping(document["addition"], "addition")
    _require_exact_keys(
        addition,
        frozenset({"compatibility_guarantee", "required_evidence"}),
        "addition",
    )
    if addition["compatibility_guarantee"] != "none":
        raise ExperimentalApiPolicyValidationError(
            "Experimental APIs must not claim stable compatibility."
        )
    _validate_evidence(addition["required_evidence"], "addition")

    promotion = _require_mapping(document["promotion"], "promotion")
    _require_exact_keys(
        promotion,
        frozenset({"minimum_minor_releases", "required_evidence", "target"}),
        "promotion",
    )
    if promotion["minimum_minor_releases"] != 1 or promotion["target"] != "stable":
        raise ExperimentalApiPolicyValidationError("promotion rules have drifted.")
    _validate_evidence(promotion["required_evidence"], "promotion")

    removal = _require_mapping(document["removal"], "removal")
    _require_exact_keys(
        removal,
        frozenset(
            {
                "allowed_release",
                "minimum_deprecation_minor_releases",
                "rename_treatment",
                "required_evidence",
            }
        ),
        "removal",
    )
    expected_removal: dict[str, object] = {
        "allowed_release": "minor_or_major",
        "minimum_deprecation_minor_releases": 1,
        "rename_treatment": "removal_and_addition",
    }
    for key, expected in expected_removal.items():
        if removal[key] != expected:
            raise ExperimentalApiPolicyValidationError(f"removal.{key} has drifted.")
    _validate_evidence(removal["required_evidence"], "removal")


def main() -> int:
    """Return success only when the experimental API policy is complete."""
    try:
        _validate_policy()
    except ExperimentalApiPolicyValidationError as error:
        print(f"Experimental API policy is invalid: {error}")
        return 1

    print("Experimental API policy is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
