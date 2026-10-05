"""Validate Mconet's one-way logical module dependencies."""

from __future__ import annotations

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
)


def _module_name(path: Path) -> str:
    # Convert a source path into its absolute package name.
    relative = path.relative_to(_SOURCE_ROOT.parent).with_suffix("")
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


def main() -> int:
    """Return a nonzero status when an internal import violates a layer rule."""
    # Parse every production module and report all violations in one invocation.
    violations: list[str] = []
    for path in sorted(_SOURCE_ROOT.rglob("*.py")):
        module = _module_name(path)
        rule = _rule_for(module)
        if rule is None:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for line_number, imported in _imported_modules(tree):
            if not imported.startswith("mconet."):
                continue
            if any(_matches_prefix(imported, prefix) for prefix in rule.allowed):
                continue
            relative_path = path.relative_to(_PROJECT_ROOT)
            violations.append(
                f"{relative_path}:{line_number}: {module} cannot import {imported}"
            )

    if violations:
        print("Import boundary violations:")
        for violation in violations:
            print(f"- {violation}")
        return 1

    print("Import boundaries are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
