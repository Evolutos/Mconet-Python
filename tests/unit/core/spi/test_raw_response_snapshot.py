"""Raw response snapshots keep bytes and metadata read-only."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

from mconet.core.domain import Bytes, Headers, OpenIdentifier
from mconet.core.spi import (
    RawResponseSnapshot,
    TransportOutcome,
    TransportResponseMetadata,
)


def test_snapshot_retains_body_and_metadata_without_mutation() -> None:
    """Verify an opted-in snapshot stores the supplied values and rejects writes."""
    metadata = TransportResponseMetadata(
        TransportOutcome(OpenIdentifier("success")),
        Headers(),
    )
    body = Bytes(b"{}")
    snapshot = RawResponseSnapshot(body, metadata)

    assert snapshot.body is body or snapshot.body == body
    assert snapshot.body == b"{}"
    assert snapshot.metadata is metadata
    try:
        setattr(snapshot, "body", Bytes(b"changed"))
    except FrozenInstanceError:
        pass
    else:
        raise AssertionError("Expected the snapshot body to be read-only.")
    assert snapshot.body == b"{}"
