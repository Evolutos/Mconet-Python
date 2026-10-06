"""Validate the frozen SemVer and Python version policy."""

from __future__ import annotations

import json
import re
import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import TypeAlias, cast

JsonValue: TypeAlias = (
    bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"] | None
)

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_POLICY_PATH = _PROJECT_ROOT / "spec" / "compatibility" / "version-policy.json"
_PYPROJECT_PATH = _PROJECT_ROOT / "pyproject.toml"
_EXPECTED_EQUIVALENCE = (
    ("MAJOR.MINOR.PATCH", "MAJOR.MINOR.PATCH"),
    ("MAJOR.MINOR.PATCH-alpha.N", "MAJOR.MINOR.PATCHaN"),
    ("MAJOR.MINOR.PATCH-beta.N", "MAJOR.MINOR.PATCHbN"),
    ("MAJOR.MINOR.PATCH-rc.N", "MAJOR.MINOR.PATCHrcN"),
    ("MAJOR.MINOR.PATCH-dev.N", "MAJOR.MINOR.PATCH.devN"),
)
_EXPECTED_ROLLBACK: dict[str, str] = {
    "failed_release_visibility": "yank",
    "prerelease_replacement": "increment_prerelease",
    "published_artifacts": "immutable",
    "stable_replacement": "increment_patch",
    "version_reuse": "forbidden",
}
_PYTHON_VERSION = re.compile(
    r"(?P<base>(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*))"
    r"(?:(?P<pre>a|b|rc)(?P<pre_number>0|[1-9]\d*))?"
    r"(?:\.dev(?P<dev_number>0|[1-9]\d*))?"
)


class VersionPolicyValidationError(ValueError):
    """Report an invalid policy or unsupported project version."""


def _require_exact_keys(
    document: Mapping[str, object], expected: frozenset[str], location: str
) -> None:
    """Reject missing or undocumented version-policy fields."""
    actual = frozenset(document)
    if actual != expected:
        missing = sorted(expected - actual)
        unexpected = sorted(actual - expected)
        raise VersionPolicyValidationError(
            f"Invalid fields in {location}: missing={missing}, unexpected={unexpected}."
        )


def _require_mapping(value: object, location: str) -> dict[str, object]:
    """Return a string-keyed mapping from JSON or TOML input."""
    if not isinstance(value, dict):
        raise VersionPolicyValidationError(f"Expected an object at {location}.")

    mapping: dict[str, object] = {}
    for key, item in cast(dict[object, object], value).items():
        if not isinstance(key, str):
            raise VersionPolicyValidationError(
                f"Expected only string keys at {location}."
            )
        mapping[key] = item
    return mapping


def _load_policy() -> dict[str, object]:
    """Load the version policy through a typed JSON boundary."""
    try:
        raw_document: object = json.loads(_POLICY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise VersionPolicyValidationError(
            f"Cannot read valid JSON from {_POLICY_PATH}: {error}"
        ) from error
    return _require_mapping(raw_document, str(_POLICY_PATH))


def _load_project_version() -> str:
    """Read the only approved Python package version source."""
    try:
        raw_document: object = tomllib.loads(
            _PYPROJECT_PATH.read_text(encoding="utf-8")
        )
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise VersionPolicyValidationError(
            f"Cannot read valid TOML from {_PYPROJECT_PATH}: {error}"
        ) from error

    pyproject = _require_mapping(raw_document, str(_PYPROJECT_PATH))
    project = _require_mapping(pyproject.get("project"), "project")
    version = project.get("version")
    if not isinstance(version, str) or not version:
        raise VersionPolicyValidationError("project.version must be non-empty.")
    return version


def _validate_equivalence(value: object) -> None:
    """Require the reviewed SemVer-to-PEP-440 stage mappings."""
    if not isinstance(value, list):
        raise VersionPolicyValidationError("equivalence must be a list.")

    mappings: list[tuple[str, str]] = []
    for index, item in enumerate(cast(list[object], value)):
        mapping = _require_mapping(item, f"equivalence[{index}]")
        _require_exact_keys(
            mapping, frozenset({"python", "semver"}), f"equivalence[{index}]"
        )
        semver = mapping["semver"]
        python = mapping["python"]
        if not isinstance(semver, str) or not isinstance(python, str):
            raise VersionPolicyValidationError(
                "equivalence entries must contain string versions."
            )
        mappings.append((semver, python))
    if tuple(mappings) != _EXPECTED_EQUIVALENCE:
        raise VersionPolicyValidationError("Version equivalence rules have drifted.")


def _to_semver(python_version: str) -> str:
    """Convert the supported PEP 440 subset to its SemVer equivalent."""
    match = _PYTHON_VERSION.fullmatch(python_version)
    if match is None:
        raise VersionPolicyValidationError(
            f"Unsupported Python version form: {python_version}."
        )

    base = match.group("base")
    prerelease = match.group("pre")
    prerelease_number = match.group("pre_number")
    development_number = match.group("dev_number")
    if prerelease is not None and development_number is not None:
        raise VersionPolicyValidationError(
            "Combined prerelease and development versions are not supported."
        )
    if development_number is not None:
        return f"{base}-dev.{development_number}"
    if prerelease is None:
        return base

    labels = {"a": "alpha", "b": "beta", "rc": "rc"}
    return f"{base}-{labels[prerelease]}.{prerelease_number}"


def _validate_conversion_examples() -> None:
    """Exercise every approved equivalence branch with a concrete version."""
    examples = {
        "1.2.3": "1.2.3",
        "1.2.3a4": "1.2.3-alpha.4",
        "1.2.3b4": "1.2.3-beta.4",
        "1.2.3rc4": "1.2.3-rc.4",
        "1.2.3.dev4": "1.2.3-dev.4",
    }
    for python_version, expected in examples.items():
        if _to_semver(python_version) != expected:
            raise VersionPolicyValidationError(
                f"Version conversion failed for {python_version}."
            )


def _validate_policy() -> str:
    """Validate policy semantics and return the current SemVer form."""
    document = _load_policy()
    _require_exact_keys(
        document,
        frozenset(
            {
                "canonical_scheme",
                "equivalence",
                "format_version",
                "platform",
                "platform_scheme",
                "release_model",
                "rollback",
                "version_source",
            }
        ),
        str(_POLICY_PATH),
    )
    expected_scalars: dict[str, object] = {
        "canonical_scheme": "semver-2.0.0",
        "format_version": 1,
        "platform": "python",
        "platform_scheme": "pep-440",
        "release_model": "lockstep",
        "version_source": "pyproject.toml:project.version",
    }
    for key, expected in expected_scalars.items():
        if document[key] != expected:
            raise VersionPolicyValidationError(f"{key} has drifted.")

    _validate_equivalence(document["equivalence"])
    _validate_conversion_examples()
    rollback = _require_mapping(document["rollback"], "rollback")
    if rollback != _EXPECTED_ROLLBACK:
        raise VersionPolicyValidationError("Rollback rules have drifted.")
    return _to_semver(_load_project_version())


def main() -> int:
    """Return success only when project versioning follows the policy."""
    try:
        semver = _validate_policy()
    except VersionPolicyValidationError as error:
        print(f"Version policy is invalid: {error}")
        return 1

    print(f"Version policy is valid; canonical version is {semver}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
