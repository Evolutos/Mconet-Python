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

    assert "- run: python scripts/build_all.py" in build_job
    assert "needs: build" in unit_job
