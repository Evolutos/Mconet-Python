"""Tests for the independently validated specification module."""

import subprocess
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_spec_module_is_valid() -> None:
    """Verify the manifest and every canonical collection index."""
    # Exercise the same standalone command used by developers and CI so the
    # checked contract cannot diverge from the documented validation path.
    result = subprocess.run(
        [sys.executable, str(_PROJECT_ROOT / "scripts" / "check_spec_module.py")],
        check=False,
        cwd=_PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
