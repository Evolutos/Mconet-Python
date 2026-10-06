"""Validate the language-neutral specification module structure."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import TypeAlias

JsonValue: TypeAlias = (
    bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"] | None
)

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SPEC_ROOT = _PROJECT_ROOT / "spec"
_MANIFEST_PATH = _SPEC_ROOT / "manifest.json"
_EXPECTED_COLLECTIONS = {
    "compatibility": Path("compatibility/index.json"),
    "errors": Path("errors/index.json"),
    "fixtures": Path("fixtures/r1-text-unary/index.json"),
    "schemas": Path("schemas/index.json"),
}
_FORMAT_VERSION = 1
_RELEASE_PROFILE = "r1.text-unary"


class SpecValidationError(ValueError):
    """Report an invalid or incomplete specification module."""


def _load_json_object(path: Path) -> dict[str, JsonValue]:
    """Load one UTF-8 JSON document and require an object at its root."""
    # A specification index must be an object so named contract fields remain
    # extensible without changing the validator's top-level parsing model.
    try:
        document: JsonValue = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SpecValidationError(
            f"Cannot read valid JSON from {path}: {error}"
        ) from error

    if not isinstance(document, dict):
        raise SpecValidationError(f"Expected a JSON object in {path}.")

    # The standard JSON decoder guarantees string keys for JSON objects; the
    # explicit root check above prevents scalar or array documents from being
    # accepted through the annotated deserialization boundary.
    return document


def _require_exact_keys(
    document: Mapping[str, object], expected: frozenset[str], path: Path
) -> None:
    """Reject missing and undocumented fields in a baseline index."""
    # Exact keys keep the module contract deterministic until a versioned
    # schema change explicitly introduces an additional field.
    actual = frozenset(document)
    if actual != expected:
        missing = sorted(expected - actual)
        unexpected = sorted(actual - expected)
        raise SpecValidationError(
            f"Invalid fields in {path}: missing={missing}, unexpected={unexpected}."
        )


def _validate_resource_list(value: JsonValue, path: Path) -> None:
    """Require a unique, sorted list of relative resource paths."""
    # Enforce one portable discovery shape for every resource collection.
    if not isinstance(value, list):
        raise SpecValidationError(f"resources must be a list of strings in {path}.")

    resources: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item:
            raise SpecValidationError(f"resources must be a list of strings in {path}.")
        resources.append(item)

    if resources != sorted(set(resources)):
        raise SpecValidationError(f"resources must be sorted and unique in {path}.")
    for item in resources:
        resource_path = Path(item)
        if resource_path.is_absolute() or ".." in resource_path.parts:
            raise SpecValidationError(
                f"Resource paths must remain inside their collection in {path}."
            )
        if not (path.parent / resource_path).is_file():
            raise SpecValidationError(f"Resource does not exist in {path}: {item}.")


def _validate_collection(name: str, relative_path: Path) -> None:
    """Validate one independently addressable specification collection."""
    # Resolve only paths declared by the fixed manifest, avoiding arbitrary
    # filesystem traversal from future untrusted manifest changes.
    path = _SPEC_ROOT / relative_path
    document = _load_json_object(path)
    expected_keys = {"collection", "format_version", "purpose", "resources"}
    if name == "fixtures":
        expected_keys.add("profile")
    _require_exact_keys(document, frozenset(expected_keys), path)

    if document["collection"] != name:
        raise SpecValidationError(f"Collection name does not match {name} in {path}.")
    if document["format_version"] != _FORMAT_VERSION:
        raise SpecValidationError(f"Unsupported format_version in {path}.")
    if not isinstance(document["purpose"], str) or not document["purpose"]:
        raise SpecValidationError(f"purpose must be a non-empty string in {path}.")
    if name == "fixtures" and document["profile"] != _RELEASE_PROFILE:
        raise SpecValidationError(
            f"Fixture profile must be {_RELEASE_PROFILE} in {path}."
        )
    _validate_resource_list(document["resources"], path)


def _validate_manifest() -> None:
    """Validate the module manifest and every declared collection index."""
    # The manifest is the stable entry point used by local checks and future
    # cross-language tooling to discover specification collections.
    document = _load_json_object(_MANIFEST_PATH)
    _require_exact_keys(
        document,
        frozenset({"collections", "format_version", "module", "profile"}),
        _MANIFEST_PATH,
    )
    if document["module"] != "mconet-spec":
        raise SpecValidationError("The spec module name must be mconet-spec.")
    if document["format_version"] != _FORMAT_VERSION:
        raise SpecValidationError("The spec module format_version must be 1.")
    if document["profile"] != _RELEASE_PROFILE:
        raise SpecValidationError(
            f"The spec module profile must be {_RELEASE_PROFILE}."
        )

    collections_value = document["collections"]
    if not isinstance(collections_value, dict):
        raise SpecValidationError("collections must be a JSON object.")

    declared: dict[str, str] = {}
    for key, value in collections_value.items():
        if not isinstance(value, str):
            raise SpecValidationError("collections must map names to string paths.")
        declared[key] = value
    expected = {name: path.as_posix() for name, path in _EXPECTED_COLLECTIONS.items()}
    if declared != expected:
        raise SpecValidationError(
            "The spec manifest must declare the canonical collection indexes."
        )

    for name, relative_path in _EXPECTED_COLLECTIONS.items():
        _validate_collection(name, relative_path)


def main() -> int:
    """Return success only when the specification module is valid."""
    # Convert validation failures into concise command-line diagnostics while
    # leaving unexpected programming errors visible to developers.
    try:
        _validate_manifest()
    except SpecValidationError as error:
        print(f"Specification module is invalid: {error}")
        return 1

    print("Specification module is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
