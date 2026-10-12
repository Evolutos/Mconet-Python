"""The public API reference covers the committed symbol baseline."""

from __future__ import annotations

import json
from pathlib import Path

_ROOT = Path(__file__).parents[2]
_REFERENCE = _ROOT / "docs" / "public-api-reference.md"
_BASELINE = _ROOT / "api" / "public-api.json"


def test_reference_lists_every_public_symbol_and_ownership_rule() -> None:
    """Verify each baseline symbol and the ownership rules are searchable."""
    text = _REFERENCE.read_text(encoding="utf-8")
    baseline = json.loads(_BASELINE.read_text(encoding="utf-8"))
    for name in baseline["symbols"]:
        assert f"### `{name}`" in text
    assert "application-owned" in text
    assert "SDK-owned" in text
    assert "include_raw_response" in text
    assert "not written" in text
