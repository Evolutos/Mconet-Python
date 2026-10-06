"""Contract tests for lint and strict static type analysis."""

import subprocess
import sys
from pathlib import Path


def test_lint_rejects_a_basic_source_defect(tmp_path: Path) -> None:
    """Verify Ruff reports a deterministic unused-import violation."""
    # Use an isolated source file so the negative test proves lint behavior
    # without introducing an intentional violation into the repository.
    source = tmp_path / "lint_failure.py"
    source.write_text("import os\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-m", "ruff", "check", str(source)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "F401" in result.stdout


def test_static_analysis_rejects_an_invalid_assignment(tmp_path: Path) -> None:
    """Verify Pyright strict mode reports an incompatible assignment."""
    # The temporary module contains one stable type error and no imports, which
    # keeps the result independent of package discovery or optional stubs.
    source = tmp_path / "type_failure.py"
    source.write_text('value: int = "not an integer"\n', encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-m", "pyright", str(source)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "reportAssignmentType" in result.stdout
