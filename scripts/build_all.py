"""Discover and build every independently packaged Mconet Python module."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SAMPLES_ROOT = _PROJECT_ROOT / "samples"


def _discover_projects() -> tuple[Path, ...]:
    """Return buildable project roots in stable dependency order."""
    # The root SDK contains all production logical modules. Samples are
    # separate consumers and therefore build only after the SDK project.
    projects = [_PROJECT_ROOT]
    projects.extend(
        manifest.parent for manifest in sorted(_SAMPLES_ROOT.glob("*/pyproject.toml"))
    )
    return tuple(projects)


def _display_path(project: Path) -> str:
    """Return a stable repository-relative label for command output."""
    # Use a single dot for the repository root so output is concise and can be
    # compared across machines without leaking absolute workspace paths.
    if project == _PROJECT_ROOT:
        return "."
    return project.relative_to(_PROJECT_ROOT).as_posix()


def _build(project: Path) -> int:
    """Build one project with the active interpreter and standard frontend."""
    # Reuse the active environment instead of assuming a global `python`
    # executable, while retaining build isolation for each project.
    result = subprocess.run(
        [sys.executable, "-m", "build", str(project)],
        check=False,
        cwd=_PROJECT_ROOT,
    )
    return result.returncode


def main() -> int:
    """List or build all discovered projects, stopping on the first failure."""
    # Listing is intentionally side-effect free so CI and tests can verify
    # discovery without creating artifacts or downloading build dependencies.
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--list",
        action="store_true",
        help="list discovered project roots without building them",
    )
    args = parser.parse_args()
    projects = _discover_projects()

    if args.list:
        for project in projects:
            print(_display_path(project))
        return 0

    for project in projects:
        label = _display_path(project)
        print(f"Building {label}...", flush=True)
        return_code = _build(project)
        if return_code != 0:
            print(f"Build failed for {label}.", file=sys.stderr)
            return return_code

    print(f"Built {len(projects)} projects successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
