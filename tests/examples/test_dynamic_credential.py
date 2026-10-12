"""The dynamic credential example reads a credential on every interaction."""

from __future__ import annotations

import asyncio
from pathlib import Path

from examples.dynamic_credential import run_dynamic_credential

_EXAMPLE = Path(__file__).parents[2] / "examples" / "dynamic_credential.py"


def test_dynamic_credential_is_read_for_each_interaction() -> None:
    """Verify two calls read twice and the example stores no secret literal."""
    source = _EXAMPLE.read_text(encoding="utf-8")
    assert "api_key" not in source
    assert "password" not in source
    assert run_dynamic_credential.__doc__ is not None
    assert asyncio.run(run_dynamic_credential()) == 4
