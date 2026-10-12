"""Write the public API reference from the committed compatibility baseline."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

_ROOT = Path(__file__).parents[1]
_BASELINE = _ROOT / "api" / "public-api.json"
_OUTPUT = _ROOT / "docs" / "public-api-reference.md"

_OWNERSHIP = """\
# Public API reference

This reference lists every public symbol in `api/public-api.json`.
Signatures include the default values recorded for that symbol.

## Ownership

- `ModelClientConfiguration.components` are application-owned. `ModelClient.close`
  does not close them.
- Components created by `make_default` and the transport created by
  `make_openai_compatible` are SDK-owned. `close` releases those builtin
  components and does not cancel an interaction that has already started.
- `InteractionOptions.components` apply to one interaction and are not written
  back onto the client configuration.
- `include_raw_response` defaults to false. A snapshot keeps the response body
  and metadata only when the caller opts in. A body past the resolved response
  limit is omitted instead of copied. `Authorization`, `Cookie`, and header
  names containing `secret` are not copied into the snapshot.
- Monitor merge defaults to `append`: client monitors, then interaction
  monitors. `prepend` reverses that order. `replace` keeps only the
  interaction monitors, and an empty replace disables the client monitors.

## Symbols

"""


def main() -> None:
    """Regenerate `docs/public-api-reference.md` from the public API baseline."""
    baseline = cast(dict[str, object], json.loads(_BASELINE.read_text(encoding="utf-8")))
    symbols = cast(dict[str, object], baseline["symbols"])
    lines = [_OWNERSHIP]
    for name in sorted(symbols):
        entry = cast(dict[str, object], symbols[name])
        lines.append(f"### `{name}`\n\n")
        lines.append(f"- Kind: `{entry['kind']}`\n")
        signature = entry.get("signature")
        if isinstance(signature, str):
            lines.append(f"- Signature: `{signature}`\n")
        member_type = entry.get("type")
        if isinstance(member_type, str):
            lines.append(f"- Type: `{member_type}`\n")
        members = cast(dict[str, object], entry.get("members") or {})
        for member_name in sorted(members):
            member = cast(dict[str, object], members[member_name])
            member_signature = member.get("signature")
            if isinstance(member_signature, str):
                lines.append(
                    f"- `{member_name}` ({member['kind']}): `{member_signature}`\n"
                )
            else:
                lines.append(f"- `{member_name}` ({member['kind']})\n")
        lines.append("\n")
    _OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    _OUTPUT.write_text("".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
