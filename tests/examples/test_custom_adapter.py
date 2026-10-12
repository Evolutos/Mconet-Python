"""The custom adapter example needs no registry or component id."""

from __future__ import annotations

import asyncio

from examples.custom_adapter import CustomTaskAdapter, run_custom_adapter


def test_custom_adapter_runs_without_a_component_id() -> None:
    """Verify the adapter instance has no id and still produces an output."""
    adapter = CustomTaskAdapter()
    assert not hasattr(adapter, "id")
    output = asyncio.run(run_custom_adapter())
    assert output.status.id.value == "completed"
