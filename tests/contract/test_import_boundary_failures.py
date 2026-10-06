"""Failure-path contract tests for module dependency enforcement."""

import subprocess
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_forbidden_dependency_fails_the_boundary_check(tmp_path: Path) -> None:
    """Verify a domain-to-transport dependency is rejected with its location."""
    # Build an isolated mconet source tree containing one intentionally invalid
    # edge, so the production tree remains valid throughout the negative test.
    source_root = tmp_path / "mconet"
    invalid_module = source_root / "core" / "domain" / "invalid.py"
    invalid_module.parent.mkdir(parents=True)
    invalid_module.write_text("import mconet.transport\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(_PROJECT_ROOT / "scripts" / "check_import_boundaries.py"),
            "--source-root",
            str(source_root),
        ],
        check=False,
        cwd=_PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert (
        "mconet/core/domain/invalid.py:1: "
        "mconet.core.domain.invalid cannot import mconet.transport"
    ) in result.stdout


def test_production_root_cannot_import_testing_module(tmp_path: Path) -> None:
    """Verify the public root cannot create a production-to-testing edge."""
    # The testing package may depend on production modules, but the reverse
    # dependency would make installed runtime behavior depend on test support.
    source_root = tmp_path / "mconet"
    source_root.mkdir()
    (source_root / "__init__.py").write_text(
        "import mconet.testing\n", encoding="utf-8"
    )

    result = subprocess.run(
        [
            sys.executable,
            str(_PROJECT_ROOT / "scripts" / "check_import_boundaries.py"),
            "--source-root",
            str(source_root),
        ],
        check=False,
        cwd=_PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "mconet cannot import mconet.testing" in result.stdout
