"""Verify candidate wheels from a clean, offline consumer environment."""

from __future__ import annotations

import os
import subprocess
import tempfile
import venv
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SDK_DIST = _PROJECT_ROOT / "dist"
_SAMPLE_DIST = _PROJECT_ROOT / "samples" / "text-unary" / "dist"
_SAMPLE_REQUIREMENT = "mconet-text-unary-sample==0.0.0"


def _environment_python(environment: Path) -> Path:
    """Return the interpreter path for a virtual environment on this platform."""
    # Python venv uses a platform-specific executable directory; selecting it
    # explicitly avoids shell activation and keeps subprocess calls portable.
    if os.name == "nt":
        return environment / "Scripts" / "python.exe"
    return environment / "bin" / "python"


def _verify_artifact_directories() -> bool:
    """Return whether both build commands produced candidate wheel directories."""
    # Fail before creating a consumer environment when package orchestration
    # was skipped or wrote artifacts to an unexpected location.
    missing = [path for path in (_SDK_DIST, _SAMPLE_DIST) if not path.is_dir()]
    if not missing:
        return True
    for path in missing:
        print(f"Missing candidate artifact directory: {path}")
    return False


def main() -> int:
    """Install and import the sample using only locally built candidate wheels."""
    # The sample's declared dependency must resolve the SDK wheel from the local
    # dist directory; --no-index prevents an installed or remote SDK from hiding
    # a broken candidate artifact.
    if not _verify_artifact_directories():
        return 1

    with tempfile.TemporaryDirectory(prefix="mconet-release-consumer-") as directory:
        environment = Path(directory)
        venv.EnvBuilder(with_pip=True).create(environment)
        python = _environment_python(environment)

        install = subprocess.run(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-index",
                "--find-links",
                str(_SDK_DIST),
                "--find-links",
                str(_SAMPLE_DIST),
                _SAMPLE_REQUIREMENT,
            ],
            check=False,
            cwd=_PROJECT_ROOT,
        )
        if install.returncode != 0:
            return install.returncode

        smoke_test = subprocess.run(
            [
                str(python),
                "-c",
                "import mconet; import mconet_text_unary_sample",
            ],
            check=False,
            cwd=environment,
        )
        if smoke_test.returncode != 0:
            return smoke_test.returncode

    print("Candidate SDK and sample artifacts passed isolated consumption.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
