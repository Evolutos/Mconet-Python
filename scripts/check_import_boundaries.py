"""Validate Mconet's one-way logical module dependencies."""

from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SOURCE_ROOT = _PROJECT_ROOT / "src" / "mconet"


@dataclass(frozen=True)
class LayerRule:
    """Allowed internal import prefixes for a logical module."""

    # The prefix selects source modules; allowed contains their valid dependencies.
    prefix: str
    allowed: frozenset[str]


_RULES = (
    LayerRule("mconet.core.domain", frozenset({"mconet.core.domain"})),
    LayerRule(
        "mconet.core.spi",
        frozenset({"mconet.core.domain", "mconet.core.spi"}),
    ),
    LayerRule(
        "mconet.core.runtime",
        frozenset({"mconet.core.domain", "mconet.core.spi", "mconet.core.runtime"}),
    ),
    LayerRule(
        "mconet.core",
        frozenset(
            {
                "mconet.core",
                "mconet.core.domain",
                "mconet.core.runtime",
                "mconet.core.spi",
            }
        ),
    ),
    LayerRule(
        "mconet.codec",
        frozenset({"mconet.core.domain", "mconet.core.spi", "mconet.codec"}),
    ),
    LayerRule(
        "mconet.transport",
        frozenset({"mconet.core.domain", "mconet.core.spi", "mconet.transport"}),
    ),
    LayerRule(
        "mconet.auth",
        frozenset({"mconet.core.domain", "mconet.core.spi", "mconet.auth"}),
    ),
    LayerRule(
        "mconet.integration",
        frozenset({"mconet.core.domain", "mconet.core.spi", "mconet.integration"}),
    ),
    LayerRule(
        "mconet.client",
        frozenset(
            {
                "mconet.auth",
                "mconet.client",
                "mconet.codec",
                "mconet.core",
                "mconet.integration",
                "mconet.transport",
            }
        ),
    ),
    LayerRule(
        "mconet.testing",
        frozenset(
            {
                "mconet.auth",
                "mconet.client",
                "mconet.codec",
                "mconet.core",
                "mconet.integration",
                "mconet.testing",
                "mconet.transport",
            }
        ),
    ),
    LayerRule(
        "mconet",
        frozenset(
            {
                "mconet.auth",
                "mconet.client",
                "mconet.codec",
                "mconet.core",
                "mconet.integration",
                "mconet.transport",
            }
        ),
    ),
)


def _module_name(path: Path, source_root: Path) -> str:
    # Convert a source path into its absolute package name.
    relative = path.relative_to(source_root.parent).with_suffix("")
    parts = relative.parts
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _imported_modules(tree: ast.AST) -> list[tuple[int, str]]:
    # Collect import locations without executing application modules.
    imports: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.append((node.lineno, node.module))
    return imports


def _matches_prefix(module: str, prefix: str) -> bool:
    # Match complete package segments instead of arbitrary string prefixes.
    return module == prefix or module.startswith(f"{prefix}.")


def _rule_for(module: str) -> LayerRule | None:
    # Specific rules appear before aggregate package rules in _RULES.
    return next(
        (rule for rule in _RULES if _matches_prefix(module, rule.prefix)),
        None,
    )


def _find_violations(source_root: Path) -> list[str]:
    """Return every forbidden internal import below one package source root."""
    # Parse every production module and report all violations in one invocation.
    violations: list[str] = []
    for path in sorted(source_root.rglob("*.py")):
        module = _module_name(path, source_root)
        rule = _rule_for(module)
        if rule is None:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for line_number, imported in _imported_modules(tree):
            if not imported.startswith("mconet."):
                continue
            if any(_matches_prefix(imported, prefix) for prefix in rule.allowed):
                continue
            relative_path = path.relative_to(source_root.parent)
            violations.append(
                f"{relative_path}:{line_number}: {module} cannot import {imported}"
            )
    return violations


def main() -> int:
    """Return a nonzero status when an internal import violates a layer rule."""
    # An overridable source root lets contract tests exercise a real violation
    # without placing intentionally invalid imports in production modules.
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-root",
        type=Path,
        default=_SOURCE_ROOT,
        help="mconet package root to inspect",
    )
    args = parser.parse_args()
    source_root: Path = args.source_root.resolve()
    if not source_root.is_dir():
        print(f"Source root does not exist or is not a directory: {source_root}")
        return 2
    violations = _find_violations(source_root)

    if violations:
        print("Import boundary violations:")
        for violation in violations:
            print(f"- {violation}")
        return 1

    print("Import boundaries are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
