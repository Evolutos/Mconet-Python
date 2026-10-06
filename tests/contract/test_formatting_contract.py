"""Contract tests for the non-mutating formatting check."""

import subprocess
import sys
from pathlib import Path


def test_format_check_rejects_without_modifying_source(tmp_path: Path) -> None:
    """Verify format check fails on invalid style and preserves file contents."""
    # Use an isolated file with deliberately invalid formatting so the test
    # proves both CI-blocking exit behavior and the absence of automatic edits.
    source = tmp_path / "unformatted.py"
    original = "def answer( ):\n return(42)\n"
    source.write_text(original, encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-m", "ruff", "format", "--check", str(source)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert source.read_text(encoding="utf-8") == original
