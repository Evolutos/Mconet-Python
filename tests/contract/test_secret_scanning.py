"""Contract tests for repository credential scanning."""

import subprocess
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SCANNER = _PROJECT_ROOT / "scripts" / "check_secrets.py"


def _run_scanner(*paths: Path) -> subprocess.CompletedProcess[str]:
    """Run the production scanner against the repository or explicit fixtures."""
    return subprocess.run(
        [sys.executable, str(_SCANNER), *(str(path) for path in paths)],
        check=False,
        cwd=_PROJECT_ROOT,
        capture_output=True,
        text=True,
    )


def test_repository_contains_no_detectable_secret() -> None:
    """Verify tracked and unignored repository files pass the scanner."""
    result = _run_scanner()
    assert result.returncode == 0, result.stdout + result.stderr


def test_fake_leak_is_detected_without_echoing_value(tmp_path: Path) -> None:
    """Verify a provider-shaped canary blocks the scan without log disclosure."""
    # Construct the canary at runtime so the test source is safe to scan.
    canary = "sk-" + ("A" * 32)
    fixture = tmp_path / "leaked.env"
    fixture.write_text(f'API_KEY="{canary}"\n', encoding="utf-8")

    result = _run_scanner(fixture)

    assert result.returncode == 1
    assert "openai-key" in result.stdout
    assert canary not in result.stdout


def test_reviewed_placeholder_is_allowed(tmp_path: Path) -> None:
    """Verify the exact S0.33 API-key placeholder does not trigger the scanner."""
    fixture = tmp_path / "tests" / "safe.env"
    fixture.parent.mkdir()
    fixture.write_text('API_KEY="mconet-test-api-key-not-secret"\n', encoding="utf-8")

    result = _run_scanner(fixture)

    assert result.returncode == 0, result.stdout + result.stderr


def test_placeholder_in_production_source_is_rejected(tmp_path: Path) -> None:
    """Verify a test placeholder cannot become a production credential default."""
    fixture = tmp_path / "src" / "config.py"
    fixture.parent.mkdir()
    fixture.write_text('API_KEY = "mconet-test-api-key-not-secret"\n', encoding="utf-8")

    result = _run_scanner(fixture)

    assert result.returncode == 1
    assert "sensitive-assignment" in result.stdout
