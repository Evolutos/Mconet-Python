"""Compare explicitly exported Python API with the committed baseline."""

from __future__ import annotations

import argparse
import importlib
import inspect
import json
import pkgutil
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SOURCE_ROOT = _PROJECT_ROOT / "src"
_BASELINE_PATH = _PROJECT_ROOT / "api" / "public-api.json"


def _signature(value: Callable[..., object]) -> str | None:
    # Some built-in and extension callables do not expose inspectable signatures.
    try:
        return str(inspect.signature(value))
    except (TypeError, ValueError):
        return None


def _class_members(value: type[object]) -> dict[str, dict[str, str | None]]:
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


def _snapshot() -> dict[str, object]:
    # Prefer the source tree to avoid comparing against an installed stale package.
    sys.path.insert(0, str(_SOURCE_ROOT))
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


def _write(snapshot: dict[str, object]) -> None:
    # Use stable formatting so baseline reviews contain deterministic diffs.
    content = json.dumps(snapshot, indent=2, sort_keys=True) + "\n"
    _BASELINE_PATH.write_text(content, encoding="utf-8")


def main() -> int:
    """Check the baseline or rewrite it when explicitly requested."""
    # Require an explicit flag before replacing the reviewed API baseline.
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--write",
        action="store_true",
        help="replace the committed baseline with the current public API",
    )
    args = parser.parse_args()
    snapshot = _snapshot()
    if args.write:
        _write(snapshot)
        print(f"Updated {_BASELINE_PATH.relative_to(_PROJECT_ROOT)}.")
        return 0

    expected = json.loads(_BASELINE_PATH.read_text(encoding="utf-8"))
    if snapshot != expected:
        print("Public API differs from api/public-api.json.")
        print("Review compatibility, then run with --write for an intentional change.")
        return 1

    print("Public API matches the committed baseline.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
