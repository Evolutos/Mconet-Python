"""Tests that response resources are released after a failing stage."""

from __future__ import annotations

from mconet.core.domain import Bytes
from mconet.core.runtime._response_resource_release import (
    ResponseResources,
    release_response_after,
)


class _Connection:
    """Count how many times one response connection is closed."""

    def __init__(self) -> None:
        """Start with the connection open."""
        self.closes = 0

    def close(self) -> None:
        """Record one close."""
        self.closes += 1


def test_stage_failures_still_release_body_and_connection() -> None:
    """Verify decode, parse, and monitor failures still release resources."""
    for stage in ("decode", "parse", "monitor"):
        connection = _Connection()
        body = Bytes(b"mconet-test-bearer-token-not-secret")
        resources = ResponseResources(body, connection.close)
        seen: list[Bytes | None] = []

        def _fail(
            current: ResponseResources = resources,
            name: str = stage,
            observed: list[Bytes | None] = seen,
        ) -> None:
            observed.append(current.body)
            raise RuntimeError(name)

        try:
            release_response_after(resources, _fail)
        except RuntimeError as error:
            assert str(error) == stage
        else:
            raise AssertionError("Expected the stage to fail.")

        assert seen == [body]
        assert resources.body is None
        assert resources.released is True
        assert connection.closes == 1
        resources.release()
        assert connection.closes == 1


def test_successful_stage_releases_resources_once() -> None:
    """Verify a completed stage also drops the body and closes once."""
    connection = _Connection()
    resources = ResponseResources(Bytes(b"{}"), connection.close)

    assert release_response_after(resources, lambda: "ok") == "ok"
    assert resources.body is None
    assert connection.closes == 1
