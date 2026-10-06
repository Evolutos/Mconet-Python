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


def test_runtime_compatibility_matches_frozen_matrix() -> None:
    """Verify package, analysis, and CI versions remain synchronized."""
    # Run the same standalone governance check used by developers and CI so a
    # minimum-version change cannot update only one consumer of the matrix.
    result = _run_script("check_runtime_compatibility.py")
    assert result.returncode == 0, result.stdout + result.stderr


def test_package_names_match_frozen_mapping() -> None:
    """Verify distribution metadata and public modules use approved names."""
    # Execute the shared governance command so local and CI validation cannot
    # disagree about which architecture modules are publicly addressable.
    result = _run_script("check_package_names.py")
    assert result.returncode == 0, result.stdout + result.stderr


def test_project_version_follows_frozen_policy() -> None:
    """Verify version syntax, equivalence, and rollback rules are approved."""
    # Use the production governance command so release metadata is checked by
    # the same rules in local runs, tests, and CI.
    result = _run_script("check_version_policy.py")
    assert result.returncode == 0, result.stdout + result.stderr


def test_experimental_api_lifecycle_matches_frozen_policy() -> None:
    """Verify experimental API changes require the approved evidence."""
    # Run the standalone policy checker used by CI so local lifecycle review
    # cannot accept rules that the build gate would reject.
    result = _run_script("check_experimental_api_policy.py")
    assert result.returncode == 0, result.stdout + result.stderr
