"""Compare explicitly exported Python API with the committed baseline."""

from __future__ import annotations

import argparse
import importlib
import inspect
import json
import pkgutil
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from types import ModuleType
from typing import cast

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SOURCE_ROOT = _PROJECT_ROOT / "src"
_BASELINE_PATH = _PROJECT_ROOT / "api" / "public-api.json"


def _signature(value: Callable[..., object]) -> str | None:
    """Return a stable inspect signature when the callable exposes one."""
    # Some built-in and extension callables do not expose inspectable signatures.
    try:
        return str(inspect.signature(value))
    except (TypeError, ValueError):
        return None


def _class_members(value: type[object]) -> dict[str, dict[str, str | None]]:
    """Describe the public callable and property surface of one class."""
    # Capture only the public callable and property surface of a class.
    members: dict[str, dict[str, str | None]] = {}
    for name, member in inspect.getmembers(value):
        if name.startswith("_"):
            continue
        if inspect.isfunction(member) or inspect.ismethod(member):
            members[name] = {"kind": "method", "signature": _signature(member)}
        elif isinstance(member, property):
            members[name] = {"kind": "property", "signature": None}
    return members


def _describe(value: object) -> dict[str, object]:
    """Describe the compatibility-relevant shape of one exported value."""
    # Preserve enough structure to detect incompatible public API changes.
    if inspect.isclass(value):
        return {
            "kind": "class",
            "members": _class_members(value),
            "signature": _signature(value),
        }
    if inspect.isfunction(value):
        return {"kind": "function", "signature": _signature(value)}
    return {"kind": "value", "type": type(value).__qualname__}


def _modules(package: ModuleType) -> list[ModuleType]:
    """Import a package and every discoverable child module in stable order."""
    # Import all package modules so each explicit __all__ export is inspected.
    discovered = [package]
    package_path = getattr(package, "__path__", None)
    if package_path is None:
        return discovered
    names = sorted(
        module_info.name
        for module_info in pkgutil.walk_packages(
            package_path,
            prefix=f"{package.__name__}.",
        )
    )
    discovered.extend(importlib.import_module(name) for name in names)
    return discovered


def _snapshot(source_root: Path) -> dict[str, object]:
    """Build a deterministic snapshot from explicitly exported Python names."""
    # Prefer the source tree to avoid comparing against an installed stale package.
    sys.path.insert(0, str(source_root))
    try:
        package = importlib.import_module("mconet")
        symbols: dict[str, dict[str, object]] = {}
        for module in _modules(package):
            exports = getattr(module, "__all__", ())
            for name in exports:
                symbols[f"{module.__name__}.{name}"] = _describe(getattr(module, name))
        return {"package": "mconet", "schema_version": 1, "symbols": symbols}
    finally:
        sys.path.pop(0)


def _write(snapshot: dict[str, object], baseline_path: Path) -> None:
    """Write a reviewed API snapshot using deterministic JSON formatting."""
    # Use stable formatting so baseline reviews contain deterministic diffs.
    content = json.dumps(snapshot, indent=2, sort_keys=True) + "\n"
    baseline_path.write_text(content, encoding="utf-8")


def _load_baseline(path: Path) -> dict[str, object]:
    """Load a committed public API baseline and require an object root."""
    try:
        raw_document: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(
            f"Cannot read valid API baseline from {path}: {error}"
        ) from error
    if not isinstance(raw_document, dict):
        raise ValueError(f"Expected an API baseline object in {path}.")
    return cast(dict[str, object], raw_document)


def _compatibility_errors(
    expected: dict[str, object], actual: dict[str, object]
) -> list[str]:
    """Return stable diagnostics for every unreviewed API snapshot change."""
    errors: list[str] = []
    for field in ("package", "schema_version"):
        if expected.get(field) != actual.get(field):
            errors.append(f"Changed baseline field: {field}.")

    expected_symbols = expected.get("symbols")
    actual_symbols = actual.get("symbols")
    if not isinstance(expected_symbols, dict) or not isinstance(actual_symbols, dict):
        return [*errors, "The baseline symbols field must be an object."]

    expected_map = cast(dict[str, object], expected_symbols)
    actual_map = cast(dict[str, object], actual_symbols)
    expected_names = frozenset(expected_map)
    actual_names = frozenset(actual_map)
    errors.extend(
        f"Removed public symbol: {name}."
        for name in sorted(expected_names - actual_names)
    )
    errors.extend(
        f"Added public symbol: {name}."
        for name in sorted(actual_names - expected_names)
    )
    errors.extend(
        f"Changed public signature or shape: {name}."
        for name in sorted(expected_names & actual_names)
        if expected_map[name] != actual_map[name]
    )
    return errors


def main(argv: Sequence[str] | None = None) -> int:
    """Check the baseline or rewrite it when explicitly requested."""
    # Require an explicit flag before replacing the reviewed API baseline.
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--write",
        action="store_true",
        help="replace the committed baseline with the current public API",
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        default=_SOURCE_ROOT,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=_BASELINE_PATH,
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args(argv)
    snapshot = _snapshot(args.source_root)
    if args.write:
        _write(snapshot, args.baseline)
        print(f"Updated {args.baseline}.")
        return 0

    try:
        expected = _load_baseline(args.baseline)
    except ValueError as error:
        print(f"Public API baseline is invalid: {error}")
        return 1
    errors = _compatibility_errors(expected, snapshot)
    if errors:
        print(f"Public API differs from {args.baseline}.")
        for error in errors:
            print(f"- {error}")
        print("Review compatibility, then run with --write for an intentional change.")
        return 1

    print("Public API matches the committed baseline.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
