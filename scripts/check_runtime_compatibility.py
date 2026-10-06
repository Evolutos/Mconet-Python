"""Validate the frozen Python language and runtime compatibility matrix."""

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
_MATRIX_PATH = _PROJECT_ROOT / "spec" / "compatibility" / "runtime-matrix.json"
_PYPROJECT_PATH = _PROJECT_ROOT / "pyproject.toml"
_CI_PATH = _PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
_EXPECTED_PLATFORM = "python"
_EXPECTED_LANGUAGE = "Python"
_EXPECTED_RUNTIME = "CPython"


class CompatibilityValidationError(ValueError):
    """Report a malformed matrix or a version declaration that has drifted."""


def _load_json_object(path: Path) -> dict[str, JsonValue]:
    """Load a UTF-8 JSON document and require an object at its root."""
    # Compatibility data is consumed by every check below, so malformed input
    # must produce one concise validation error instead of an incidental cast.
    try:
        document: JsonValue = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CompatibilityValidationError(
            f"Cannot read valid JSON from {path}: {error}"
        ) from error

    if not isinstance(document, dict):
        raise CompatibilityValidationError(f"Expected a JSON object in {path}.")
    return document


def _require_exact_keys(
    document: Mapping[str, object], expected: frozenset[str], location: str
) -> None:
    """Reject missing or undocumented compatibility fields."""
    # Exact keys make version-policy changes explicit and reviewable instead of
    # allowing an unused field to imply support that tooling does not enforce.
    actual = frozenset(document)
    if actual != expected:
        missing = sorted(expected - actual)
        unexpected = sorted(actual - expected)
        raise CompatibilityValidationError(
            f"Invalid fields in {location}: missing={missing}, unexpected={unexpected}."
        )


def _require_object(value: JsonValue, location: str) -> dict[str, JsonValue]:
    """Return a nested JSON object or report its contract location."""
    if not isinstance(value, dict):
        raise CompatibilityValidationError(f"Expected an object at {location}.")
    return value


def _require_mapping(value: object, location: str) -> dict[str, object]:
    """Return a string-keyed mapping from an untyped TOML boundary."""
    if not isinstance(value, dict):
        raise CompatibilityValidationError(f"Expected a table at {location}.")

    mapping: dict[str, object] = {}
    untyped_mapping = cast(dict[object, object], value)
    for key, item in untyped_mapping.items():
        if not isinstance(key, str):
            raise CompatibilityValidationError(
                f"Expected only string keys at {location}."
            )
        mapping[key] = item
    return mapping


def _load_matrix() -> tuple[str, tuple[str, ...]]:
    """Validate the matrix schema and return its canonical version values."""
    document = _load_json_object(_MATRIX_PATH)
    _require_exact_keys(
        document,
        frozenset({"format_version", "language", "platform", "runtime"}),
        str(_MATRIX_PATH),
    )
    if document["format_version"] != 1:
        raise CompatibilityValidationError("format_version must be 1.")
    if document["platform"] != _EXPECTED_PLATFORM:
        raise CompatibilityValidationError("platform must be python.")

    language = _require_object(document["language"], "language")
    _require_exact_keys(language, frozenset({"minimum_version", "name"}), "language")
    if language["name"] != _EXPECTED_LANGUAGE:
        raise CompatibilityValidationError("language.name must be Python.")

    runtime = _require_object(document["runtime"], "runtime")
    _require_exact_keys(
        runtime,
        frozenset({"implementation", "minimum_version", "tested_versions"}),
        "runtime",
    )
    if runtime["implementation"] != _EXPECTED_RUNTIME:
        raise CompatibilityValidationError("runtime.implementation must be CPython.")

    minimum = language["minimum_version"]
    if not isinstance(minimum, str) or not re.fullmatch(r"3\.\d+", minimum):
        raise CompatibilityValidationError(
            "language.minimum_version must be a Python 3 minor version."
        )
    if runtime["minimum_version"] != minimum:
        raise CompatibilityValidationError(
            "Language and runtime minimum versions must match."
        )

    tested_value = runtime["tested_versions"]
    if not isinstance(tested_value, list) or not tested_value:
        raise CompatibilityValidationError(
            "runtime.tested_versions must be a non-empty list."
        )
    tested_items: list[str] = []
    for version in tested_value:
        if not isinstance(version, str):
            raise CompatibilityValidationError(
                "runtime.tested_versions must contain only strings."
            )
        tested_items.append(version)
    tested = tuple(tested_items)
    if tested != tuple(sorted(set(tested))) or tested[0] != minimum:
        raise CompatibilityValidationError(
            "runtime.tested_versions must be sorted, unique, and start at the minimum."
        )
    return minimum, tested


def _validate_project_metadata(minimum: str, tested: tuple[str, ...]) -> None:
    """Require package and static-analysis metadata to match the matrix."""
    # These declarations control installation and analysis independently; all
    # of them must use the reviewed minimum to avoid accidental partial support.
    try:
        raw_pyproject: object = tomllib.loads(
            _PYPROJECT_PATH.read_text(encoding="utf-8")
        )
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise CompatibilityValidationError(
            f"Cannot read valid TOML from {_PYPROJECT_PATH}: {error}"
        ) from error

    pyproject = _require_mapping(raw_pyproject, "pyproject")
    project = _require_mapping(pyproject.get("project"), "project")
    tool = _require_mapping(pyproject.get("tool"), "tool")
    pyright = _require_mapping(tool.get("pyright"), "tool.pyright")
    ruff = _require_mapping(tool.get("ruff"), "tool.ruff")
    if project.get("requires-python") != f">={minimum}":
        raise CompatibilityValidationError("project.requires-python has drifted.")
    if pyright.get("pythonVersion") != minimum:
        raise CompatibilityValidationError("tool.pyright.pythonVersion has drifted.")
    if ruff.get("target-version") != f"py{minimum.replace('.', '')}":
        raise CompatibilityValidationError("tool.ruff.target-version has drifted.")

    classifiers = project.get("classifiers")
    if not isinstance(classifiers, list):
        raise CompatibilityValidationError("project.classifiers must be a list.")
    classifier_set: set[str] = set()
    for classifier in cast(list[object], classifiers):
        if not isinstance(classifier, str):
            raise CompatibilityValidationError(
                "project.classifiers must contain only strings."
            )
        classifier_set.add(classifier)
    expected_classifiers = {
        f"Programming Language :: Python :: {version}" for version in tested
    }
    if not expected_classifiers.issubset(classifier_set):
        raise CompatibilityValidationError(
            "Python version classifiers do not cover every tested runtime."
        )


def _validate_ci_matrix(tested: tuple[str, ...]) -> None:
    """Require the unit-test CI matrix to cover every frozen runtime."""
    # The workflow intentionally keeps its compact inline list; matching that
    # single declaration avoids a YAML dependency in this governance check.
    try:
        workflow = _CI_PATH.read_text(encoding="utf-8")
    except OSError as error:
        raise CompatibilityValidationError(
            f"Cannot read {_CI_PATH}: {error}"
        ) from error
    expected = (
        "python-version: [" + ", ".join(f'"{version}"' for version in tested) + "]"
    )
    if expected not in workflow:
        raise CompatibilityValidationError("The CI Python matrix has drifted.")


def main() -> int:
    """Return success only when every runtime declaration matches the matrix."""
    # Keep command-line failures concise while preserving unexpected programming
    # errors for normal traceback-based diagnosis.
    try:
        minimum, tested = _load_matrix()
        _validate_project_metadata(minimum, tested)
        _validate_ci_matrix(tested)
    except CompatibilityValidationError as error:
        print(f"Runtime compatibility is invalid: {error}")
        return 1

    print("Runtime compatibility is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
