"""The company transport example injects one library at both scopes."""

from __future__ import annotations

import asyncio

from examples.company_http_transport import run_company_transport_injections


def test_company_transport_works_at_client_and_call_scope() -> None:
    """Verify the client default and the one-call override both send."""
    client_name, call_name = asyncio.run(run_company_transport_injections())
    assert client_name == "client"
    assert call_name == "call"
