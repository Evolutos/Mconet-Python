"""Validate the frozen Python distribution and import namespace mapping."""

from __future__ import annotations

import json
import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import TypeAlias, cast

JsonValue: TypeAlias = (
    bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"] | None
)

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_MAPPING_PATH = _PROJECT_ROOT / "spec" / "compatibility" / "package-names.json"
_PYPROJECT_PATH = _PROJECT_ROOT / "pyproject.toml"
_SOURCE_ROOT = _PROJECT_ROOT / "src"
_EXPECTED_PLATFORM = "python"


class PackageNameValidationError(ValueError):
    """Report an invalid package map or a conflicting project declaration."""


def _require_exact_keys(
    document: Mapping[str, object], expected: frozenset[str], location: str
) -> None:
    """Reject missing or undocumented fields at a mapping boundary."""
    actual = frozenset(document)
    if actual != expected:
        missing = sorted(expected - actual)
        unexpected = sorted(actual - expected)
        raise PackageNameValidationError(
            f"Invalid fields in {location}: missing={missing}, unexpected={unexpected}."
        )


def _require_mapping(value: object, location: str) -> dict[str, object]:
    """Return a string-keyed mapping from an untyped data boundary."""
    if not isinstance(value, dict):
        raise PackageNameValidationError(f"Expected an object at {location}.")

    mapping: dict[str, object] = {}
    for key, item in cast(dict[object, object], value).items():
        if not isinstance(key, str):
            raise PackageNameValidationError(
                f"Expected only string keys at {location}."
            )
        mapping[key] = item
    return mapping


def _load_json_mapping() -> dict[str, object]:
    """Load the package-name resource as a validated root object."""
    try:
        raw_document: object = json.loads(_MAPPING_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PackageNameValidationError(
            f"Cannot read valid JSON from {_MAPPING_PATH}: {error}"
        ) from error
    return _require_mapping(raw_document, str(_MAPPING_PATH))


def _load_pyproject() -> dict[str, object]:
    """Load project metadata without leaking an untyped TOML result."""
    try:
        raw_document: object = tomllib.loads(
            _PYPROJECT_PATH.read_text(encoding="utf-8")
        )
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise PackageNameValidationError(
            f"Cannot read valid TOML from {_PYPROJECT_PATH}: {error}"
        ) from error
    return _require_mapping(raw_document, str(_PYPROJECT_PATH))


def _discover_leaf_modules(namespace: str) -> frozenset[str]:
    """Discover implemented leaf packages below the frozen import namespace."""
    # Architecture modules are leaf packages; intermediate namespace packages
    # remain implementation structure and therefore do not need separate IDs.
    namespace_root = _SOURCE_ROOT / namespace
    if not (namespace_root / "__init__.py").is_file():
        raise PackageNameValidationError(
            f"Import namespace does not exist: {namespace}."
        )

    modules: set[str] = set()
    for initializer in namespace_root.rglob("__init__.py"):
        package_dir = initializer.parent
        has_child_package = any(
            child.is_dir() and (child / "__init__.py").is_file()
            for child in package_dir.iterdir()
        )
        if has_child_package:
            continue
        relative = package_dir.relative_to(_SOURCE_ROOT)
        modules.add(".".join(relative.parts))
    return frozenset(modules)


def _validate_mapping() -> None:
    """Cross-check the frozen names against metadata and source packages."""
    document = _load_json_mapping()
    _require_exact_keys(
        document,
        frozenset(
            {
                "distribution_name",
                "format_version",
                "import_namespace",
                "platform",
                "public_modules",
            }
        ),
        str(_MAPPING_PATH),
    )
    if document["format_version"] != 1:
        raise PackageNameValidationError("format_version must be 1.")
    if document["platform"] != _EXPECTED_PLATFORM:
        raise PackageNameValidationError("platform must be python.")

    distribution_name = document["distribution_name"]
    import_namespace = document["import_namespace"]
    if not isinstance(distribution_name, str) or not distribution_name:
        raise PackageNameValidationError("distribution_name must be non-empty.")
    if not isinstance(import_namespace, str) or not import_namespace.isidentifier():
        raise PackageNameValidationError(
            "import_namespace must be a valid Python identifier."
        )

    public_modules = _require_mapping(document["public_modules"], "public_modules")
    if not public_modules:
        raise PackageNameValidationError("public_modules must not be empty.")
    module_names: list[str] = []
    for architecture_name, module_name in public_modules.items():
        if not architecture_name or not isinstance(module_name, str):
            raise PackageNameValidationError(
                "public_modules must map non-empty IDs to module names."
            )
        if not module_name.startswith(f"{import_namespace}."):
            raise PackageNameValidationError(
                f"Public module escapes the {import_namespace} namespace."
            )
        if any(not part.isidentifier() for part in module_name.split(".")):
            raise PackageNameValidationError(
                f"Invalid Python module name: {module_name}."
            )
        module_names.append(module_name)
    if len(module_names) != len(set(module_names)):
        raise PackageNameValidationError("Public module names must be unique.")

    pyproject = _load_pyproject()
    project = _require_mapping(pyproject.get("project"), "project")
    if project.get("name") != distribution_name:
        raise PackageNameValidationError("project.name has drifted.")
    tool = _require_mapping(pyproject.get("tool"), "tool")
    hatch = _require_mapping(tool.get("hatch"), "tool.hatch")
    build = _require_mapping(hatch.get("build"), "tool.hatch.build")
    targets = _require_mapping(build.get("targets"), "tool.hatch.build.targets")
    wheel = _require_mapping(targets.get("wheel"), "tool.hatch.build.targets.wheel")
    package_roots = wheel.get("packages")
    expected_package_roots = [f"src/{import_namespace}"]
    if package_roots != expected_package_roots:
        raise PackageNameValidationError("Wheel package root has drifted.")

    discovered = _discover_leaf_modules(import_namespace)
    if frozenset(module_names) != discovered:
        missing = sorted(discovered - frozenset(module_names))
        unexpected = sorted(frozenset(module_names) - discovered)
        raise PackageNameValidationError(
            f"Public module mapping has drifted: missing={missing}, "
            f"unexpected={unexpected}."
        )


def main() -> int:
    """Return success only when package names match the frozen mapping."""
    try:
        _validate_mapping()
    except PackageNameValidationError as error:
        print(f"Package names are invalid: {error}")
        return 1

    print("Package names are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
