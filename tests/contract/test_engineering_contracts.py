"""S0 architecture enforcement contract tests."""

import subprocess
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _run_script(name: str) -> subprocess.CompletedProcess[str]:
    # Use the active test interpreter and capture diagnostics for failed assertions.
    return subprocess.run(
        [sys.executable, str(_PROJECT_ROOT / "scripts" / name)],
        check=False,
        cwd=_PROJECT_ROOT,
        capture_output=True,
        text=True,
    )


def test_import_boundaries_are_valid() -> None:
    # Keep production dependencies aligned with the architecture layers.
    result = _run_script("check_import_boundaries.py")
    assert result.returncode == 0, result.stdout + result.stderr


def test_public_api_matches_baseline() -> None:
    # Require explicit review for every exported API change.
    result = _run_script("check_api_compatibility.py")
    assert result.returncode == 0, result.stdout + result.stderr
