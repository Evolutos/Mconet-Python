"""Run engineering contracts and component contract suites as one CI stage."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def contract_pytest_arguments(root: Path, report: Path) -> list[str]:
    """Build the contract-stage pytest command for one checkout.

    Args:
        root: Repository root that contains ``tests/contract`` and the suites.
        report: JUnit report path written by this stage.

    Returns:
        The argument vector, including the interpreter and pytest module.

    Raises:
        FileNotFoundError: If the checkout has no component contract suites.
    """
    suite_root = root / "tests" / "unit" / "testing"
    suites = sorted(suite_root.glob("test_*_contract_suite.py"))
    if not suites:
        # An empty selection would make the contract stage pass without running
        # the test kit. Fail before pytest starts.
        raise FileNotFoundError("No component contract suites were found.")
    return [
        sys.executable,
        "-m",
        "pytest",
        str(root / "tests" / "contract"),
        *[str(path) for path in suites],
        f"--junitxml={report}",
        "-ra",
    ]


def main() -> int:
    """Run the contract stage and preserve pytest's exit status."""
    root = Path(__file__).resolve().parents[1]
    report = root / "contract-report.xml"
    try:
        command = contract_pytest_arguments(root, report)
    except FileNotFoundError as error:
        print(str(error), file=sys.stderr)
        return 1
    completed = subprocess.run(command, cwd=root, check=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
