"""CI contract entry and rendered suite-failure location."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import cast

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _contract_pytest_arguments(root: Path, report: Path) -> list[str]:
    """Load the CI argument builder without making scripts a package."""
    path = _PROJECT_ROOT / "scripts" / "run_contract_ci.py"
    spec = importlib.util.spec_from_file_location("run_contract_ci", path)
    if spec is None or spec.loader is None:
        raise AssertionError("The contract CI entry could not be loaded.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    builder = getattr(module, "contract_pytest_arguments", None)
    if not callable(builder):
        raise AssertionError("contract_pytest_arguments is missing.")
    arguments = builder(root, report)
    if not isinstance(arguments, list):
        raise AssertionError("contract_pytest_arguments must return a list.")
    return cast(list[str], arguments)


def test_contract_stage_command_includes_engineering_and_component_suites() -> None:
    """Select every component suite without dropping the engineering contracts."""
    report = _PROJECT_ROOT / "contract-report.xml"
    arguments = _contract_pytest_arguments(_PROJECT_ROOT, report)
    suites = sorted(
        path.name
        for path in (_PROJECT_ROOT / "tests" / "unit" / "testing").glob(
            "test_*_contract_suite.py"
        )
    )

    assert arguments[:3] == [sys.executable, "-m", "pytest"]
    assert str(_PROJECT_ROOT / "tests" / "contract") in arguments
    assert f"--junitxml={report}" in arguments
    for suite in suites:
        assert any(argument.endswith(suite) for argument in arguments)


def test_failing_suite_case_names_component_and_fixture_in_report() -> None:
    """Show the component and fixture on a real pytest failure and in JUnit."""
    probe_dir = _PROJECT_ROOT / "tests" / "_contract_location_probe"
    probe = probe_dir / "test_adapter_contract_suite.py"
    report = probe_dir / "probe-report.xml"
    probe_dir.mkdir()
    probe.write_text(
        "def test_location_probe() -> None:\n    raise AssertionError('boom')\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                str(probe),
                f"--junitxml={report}",
                "-p",
                "no:cacheprovider",
                "--tb=short",
            ],
            cwd=_PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )
        output = completed.stdout + completed.stderr
        assert completed.returncode != 0
        assert "component=task_protocol_adapter fixture=test_location_probe" in output

        document = ET.parse(report)
        properties = {
            (item.get("name"), item.get("value")) for item in document.iter("property")
        }
        assert ("component", "task_protocol_adapter") in properties
        assert ("fixture", "test_location_probe") in properties
    finally:
        if probe_dir.exists():
            for path in sorted(probe_dir.rglob("*"), reverse=True):
                if path.is_file():
                    path.unlink()
                else:
                    path.rmdir()
            probe_dir.rmdir()
