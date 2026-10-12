"""A decoding failure still releases the response body and connection."""

from __future__ import annotations

from typing import cast

from mconet.core.domain import Bytes, ModelInteractionError
from mconet.core.runtime._decoding_failure_release import run_response_decoding
from mconet.core.runtime._interaction_terminal_machine import (
    InteractionTerminalMachine,
)
from mconet.core.runtime._response_resource_release import ResponseResources
from mconet.core.spi import ComponentDescriptor, ErasedRuntimeValue, PayloadDecoder


class _Decoder:
    """Decoder whose failure text must not be required for release."""

    def __init__(self) -> None:
        """Store decoder metadata."""
        self.descriptor = ComponentDescriptor("decoder", "1.0.0", "application")

    def decode(self, raw_data: Bytes) -> ErasedRuntimeValue:
        """Fail with the body text so the wrapper can hide it."""
        raise RuntimeError(raw_data.decode("ascii"))


class _Connection:
    """Count connection closes."""

    def __init__(self) -> None:
        """Start open."""
        self.closes = 0

    def close(self) -> None:
        """Record one close."""
        self.closes += 1


def test_decoding_failure_releases_response_resources() -> None:
    """Verify a decode error drops the body and closes the connection."""
    connection = _Connection()
    body = Bytes(b"mconet-test-bearer-token-not-secret")
    resources = ResponseResources(body, connection.close)
    machine = InteractionTerminalMachine()
    try:
        run_response_decoding(
            cast(PayloadDecoder, _Decoder()), body, resources, machine
        )
    except ModelInteractionError as error:
        raised = error
    else:
        raise AssertionError("Expected decoding to fail.")

    assert raised.code == "payload_decoding_failed"
    assert "mconet-test-bearer-token-not-secret" not in raised.message
    assert resources.body is None
    assert resources.released is True
    assert connection.closes == 1
    assert machine.state is not None
    assert machine.state.failed is True
