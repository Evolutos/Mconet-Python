"""The simplest-call example runs through the public client API."""

from __future__ import annotations

import ast
import asyncio
import json
from pathlib import Path

from examples.simplest_call import run_simplest_call

from mconet.core.domain import HeaderField, Headers
from mconet.testing import MockHttpResponseScript, MockHttpServer

_EXAMPLE = Path(__file__).parents[2] / "examples" / "simplest_call.py"


def test_simplest_call_uses_only_the_public_api() -> None:
    """Verify the example imports no private module and completes one call."""
    tree = ast.parse(_EXAMPLE.read_text(encoding="utf-8"))
    modules = [
        node.module
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
        and node.module is not None
        and node.module.startswith("mconet")
    ]
    assert modules
    assert all("._" not in module for module in modules)
    imported = [
        alias.name
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
        and node.module is not None
        and node.module.startswith("mconet")
        for alias in node.names
    ]
    assert all(not name.startswith("_") for name in imported)
    response = {
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Hi"},
                "finish_reason": "stop",
            }
        ]
    }
    script = MockHttpResponseScript(
        status_code=200,
        headers=Headers((HeaderField("Content-Type", "application/json"),)),
        body=json.dumps(response).encode("utf-8"),
    )
    with MockHttpServer((script,)) as server:
        output = asyncio.run(run_simplest_call(server.uri))
        recorded = server.requests
    assert output.stop_reason == "stop"
    assert len(recorded) == 1
    assert b"Hello" in recorded[0].body
