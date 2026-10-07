"""Stable structural comparison for redacted JSON snapshots."""

from __future__ import annotations

from mconet.core.domain import JsonValue
from mconet.testing.json_fixture import json_fixtures_equal


class SnapshotComparator:
    """Compare caller-redacted snapshots with canonical JSON semantics.

    Snapshots are accepted only as decoded :class:`~mconet.core.domain.JsonValue`
    data. Object insertion order is ignored recursively, array order remains
    significant, and portable integers and finite floating-point values share
    the JSON number kind. The comparator is stateless, so one instance can be
    reused safely without retaining snapshot contents or comparison outcomes.

    Redaction deliberately remains outside this type: callers must remove or
    replace secrets before comparison. This boundary prevents a testing helper
    from defining security policy or retaining sensitive pre-redaction values.
    The comparator also does not serialize, update, diff, or persist snapshots.
    """

    __slots__ = ()

    def compare(self, actual: JsonValue, expected: JsonValue) -> bool:
        """Return whether two redacted snapshots have the same JSON structure.

        Args:
            actual: Decoded, already-redacted snapshot produced by the test.
            expected: Decoded, already-redacted reference snapshot.

        Returns:
            ``True`` when the snapshots are canonically equal.

        Raises:
            TypeError: If either snapshot is not structurally valid JSON data.
            ValueError: If either snapshot contains a non-portable JSON number.
        """
        # Delegate to the single canonical fixture implementation so snapshot
        # assertions cannot drift from the SDK's cross-language JSON contract.
        return json_fixtures_equal(actual, expected)
