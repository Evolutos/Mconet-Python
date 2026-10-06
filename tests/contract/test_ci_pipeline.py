"""Contract tests for the staged CI pipeline."""

from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOW_PATH = _PROJECT_ROOT / ".github" / "workflows" / "ci.yml"


def _job_block(name: str, next_name: str) -> str:
    """Extract one top-level job block from the repository CI workflow."""
    # Job names are stable architecture identifiers, so bounded text extraction
    # avoids adding a YAML runtime dependency solely for governance tests.
    workflow = _WORKFLOW_PATH.read_text(encoding="utf-8")
    start = workflow.index(f"  {name}:\n")
    end = workflow.index(f"  {next_name}:\n", start)
    return workflow[start:end]


def test_build_stage_blocks_unit_until_all_projects_build() -> None:
    """Verify unit tests depend on successful root build orchestration."""
    # The build job must use the same documented command as local development;
    # the unit job's needs edge makes any nonzero build result block execution.
    build_job = _job_block("build", "unit")
    unit_job = _job_block("unit", "contract")

    assert "- run: python scripts/check_runtime_compatibility.py" in build_job
    assert "- run: python scripts/build_all.py" in build_job
    assert "needs: build" in unit_job


def test_unit_stage_blocks_contract_across_supported_python_versions() -> None:
    """Verify the unit matrix and its blocking edge to contract tests."""
    # Each supported interpreter must execute the same unit entry point; the
    # contract stage may start only after every matrix entry succeeds.
    unit_job = _job_block("unit", "contract")
    contract_job = _job_block("contract", "conformance")

    assert 'python-version: ["3.11", "3.12", "3.13", "3.14"]' in unit_job
    assert "- run: pytest tests/unit --cov=mconet --cov-report=term-missing" in unit_job
    assert "needs: unit" in contract_job


def test_contract_stage_is_independent_and_blocks_conformance() -> None:
    """Verify contract failures are isolated and block conformance tests."""
    # A dedicated job and test path make failures attributable to component
    # contracts instead of mixing them into unit or conformance diagnostics.
    contract_job = _job_block("contract", "conformance")
    conformance_job = _job_block("conformance", "package")

    assert "name: Contract" in contract_job
    assert "needs: unit" in contract_job
    assert "- run: pytest tests/contract" in contract_job
    assert "needs: contract" in conformance_job


def test_conformance_stage_reports_differences_and_blocks_packaging() -> None:
    """Verify conformance always publishes a report before packaging."""
    # JUnit retains stable pytest node identifiers for fixture differences, and
    # `always()` preserves the report even when the test command fails.
    conformance_job = _job_block("conformance", "package")
    workflow = _WORKFLOW_PATH.read_text(encoding="utf-8")
    package_start = workflow.index("  package:\n")
    package_job = workflow[package_start:]

    assert "needs: contract" in conformance_job
    assert (
        "- run: pytest tests/conformance --junitxml=conformance-report.xml"
        in conformance_job
    )
    assert "name: conformance-report" in conformance_job
    assert "path: conformance-report.xml" in conformance_job
    assert "if: always()" in conformance_job
    assert "needs: conformance" in package_job


def test_package_stage_builds_and_consumes_all_candidate_artifacts() -> None:
    """Verify packaging tests SDK and sample wheels in an isolated consumer."""
    # The package job must exercise local candidate dependency resolution before
    # uploading both projects, rather than importing the editable checkout.
    workflow = _WORKFLOW_PATH.read_text(encoding="utf-8")
    package_start = workflow.index("  package:\n")
    package_job = workflow[package_start:]

    assert "needs: conformance" in package_job
    assert "- run: python scripts/build_all.py" in package_job
    assert "- run: python scripts/verify_release_consumption.py" in package_job
    assert "name: distributions" in package_job
    assert "dist/" in package_job
    assert "samples/text-unary/dist/" in package_job
