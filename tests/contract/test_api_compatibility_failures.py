"""Failure-path contracts for the public API compatibility gate."""

import json
import subprocess
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_CHECKER = _PROJECT_ROOT / "scripts" / "check_api_compatibility.py"


def _run_checker(source_root: Path, baseline: Path) -> subprocess.CompletedProcess[str]:
    """Run the compatibility checker against an isolated fixture package."""
    return subprocess.run(
        [
            sys.executable,
            str(_CHECKER),
            "--source-root",
            str(source_root),
            "--baseline",
            str(baseline),
        ],
        check=False,
        cwd=_PROJECT_ROOT,
        capture_output=True,
        text=True,
    )


def _write_module(source_root: Path, content: str) -> None:
    """Create the isolated mconet module used by one failure scenario."""
    package = source_root / "mconet"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text(content, encoding="utf-8")


def _write_baseline(path: Path, signature: str) -> None:
    """Write a minimal reviewed function baseline for failure testing."""
    baseline = {
        "package": "mconet",
        "schema_version": 1,
        "symbols": {
            "mconet.execute": {
                "kind": "function",
                "signature": signature,
            }
        },
    }
    path.write_text(json.dumps(baseline), encoding="utf-8")


def test_removed_public_symbol_fails_compatibility_check(tmp_path: Path) -> None:
    """Verify deleting a reviewed export produces a stable blocking error."""
    source_root = tmp_path / "src"
    baseline = tmp_path / "public-api.json"
    _write_module(source_root, "__all__: tuple[str, ...] = ()\n")
    _write_baseline(baseline, "(value: str) -> str")

    result = _run_checker(source_root, baseline)

    assert result.returncode == 1
    assert "Removed public symbol: mconet.execute." in result.stdout


def test_changed_public_signature_fails_compatibility_check(tmp_path: Path) -> None:
    """Verify changing a reviewed callable signature blocks the build."""
    source_root = tmp_path / "src"
    baseline = tmp_path / "public-api.json"
    _write_module(
        source_root,
        "def execute(value: str, timeout: float = 1.0) -> str:\n"
        "    return value\n\n"
        '__all__ = ("execute",)\n',
    )
    _write_baseline(baseline, "(value: str) -> str")

    result = _run_checker(source_root, baseline)

    assert result.returncode == 1
    assert "Changed public signature or shape: mconet.execute." in result.stdout
