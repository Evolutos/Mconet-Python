"""Tests for the S0 root build orchestration."""

import subprocess
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_build_orchestration_discovers_every_project() -> None:
    """Verify root-first discovery includes each independent sample project."""
    # Exercise the documented command boundary while using its side-effect-free
    # listing mode so unit tests do not perform nested isolated builds.
    result = subprocess.run(
        [sys.executable, str(_PROJECT_ROOT / "scripts" / "build_all.py"), "--list"],
        check=False,
        cwd=_PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.splitlines() == [".", "samples/text-unary"]
