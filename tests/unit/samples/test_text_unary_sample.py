"""Tests for the independently buildable S0 text-unary sample module."""

from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_SAMPLE_ROOT = _PROJECT_ROOT / "samples" / "text-unary"


def test_text_unary_sample_depends_only_on_published_sdk() -> None:
    """Verify the sample does not import the repository source tree directly."""
    # Exact metadata assertions keep the sample a genuine external consumer;
    # local path dependencies would hide packaging and public API defects.
    configuration = (_SAMPLE_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert 'dependencies = ["mconet-sdk==0.1.0.dev0"]' in configuration
    assert "../../src" not in configuration
    assert "../../../src" not in configuration
    assert 'name = "Mcont"' in configuration
    assert 'email = "Mcont@gmail.com"' in configuration
