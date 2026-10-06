"""Detect committed credentials while allowing reviewed test placeholders."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_PLACEHOLDER_POLICY = (
    _PROJECT_ROOT / "spec" / "compatibility" / "test-secret-placeholders.json"
)
_SENSITIVE_ASSIGNMENT = re.compile(
    r"(?i)[\"']?(?:api[_-]?key|client[_-]?secret|signing[_-]?secret|secret|"
    r"access[_-]?token|bearer[_-]?token|password|credential)"
    r"[\"']?\s*[:=]\s*[\"'](?P<value>[^\"'\r\n]{12,})[\"']"
)


@dataclass(frozen=True, slots=True)
class SecretPattern:
    """Describe one named credential pattern without retaining matched values."""

    name: str
    expression: re.Pattern[str]


@dataclass(frozen=True, slots=True)
class Finding:
    """Identify a potential leak by file, line, and non-sensitive rule name."""

    path: Path
    line: int
    pattern: str


_PATTERNS = (
    SecretPattern(
        "private-key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")
    ),
    SecretPattern("openai-key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    SecretPattern("aws-access-key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    SecretPattern("google-api-key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    SecretPattern("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,255}\b")),
    SecretPattern("github-pat", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{22,255}\b")),
    SecretPattern("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
    SecretPattern("bearer-token", re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~-]{20,}")),
    SecretPattern(
        "credential-url",
        re.compile(r"\bhttps?://[^\s/:@]+:[^\s/@]+@[^\s/]+"),
    ),
)


class SecretScanError(RuntimeError):
    """Report scanner configuration or repository discovery failures."""


def _load_allowed_placeholders() -> frozenset[str]:
    """Load the exact committed literals approved by the S0.33 policy."""
    try:
        raw_document: object = json.loads(
            _PLACEHOLDER_POLICY.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as error:
        raise SecretScanError(
            f"Cannot read placeholder policy {_PLACEHOLDER_POLICY}: {error}"
        ) from error
    if not isinstance(raw_document, dict):
        raise SecretScanError("Placeholder policy must be a JSON object.")

    document = cast(dict[object, object], raw_document)
    raw_placeholders = document.get("placeholders")
    if not isinstance(raw_placeholders, dict):
        raise SecretScanError("Placeholder policy must define placeholders.")

    placeholders: set[str] = set()
    for value in cast(dict[object, object], raw_placeholders).values():
        if not isinstance(value, str) or not value:
            raise SecretScanError("Every approved placeholder must be non-empty.")
        placeholders.add(value)
    if not placeholders:
        raise SecretScanError("At least one approved placeholder is required.")
    return frozenset(placeholders)


def _repository_files() -> tuple[Path, ...]:
    """Return tracked and unignored untracked files from the current worktree."""
    # Including untracked files catches a leak before `git add`; ignored build,
    # cache, environment, and distribution outputs remain outside the scan.
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        check=False,
        cwd=_PROJECT_ROOT,
        capture_output=True,
    )
    if result.returncode != 0:
        diagnostic = result.stderr.decode("utf-8", errors="replace").strip()
        raise SecretScanError(f"Cannot enumerate repository files: {diagnostic}")
    names = result.stdout.decode("utf-8").split("\0")
    return tuple(_PROJECT_ROOT / name for name in names if name)


def _explicit_files(paths: Sequence[Path]) -> tuple[Path, ...]:
    """Expand explicit files or directories for isolated contract testing."""
    files: set[Path] = set()
    for path in paths:
        resolved = path.resolve()
        if resolved.is_file():
            files.add(resolved)
        elif resolved.is_dir():
            files.update(
                candidate for candidate in resolved.rglob("*") if candidate.is_file()
            )
        else:
            raise SecretScanError(f"Scan path does not exist: {path}")
    return tuple(sorted(files))


def _line_number(text: str, position: int) -> int:
    """Convert a match offset into a one-based line number."""
    return text.count("\n", 0, position) + 1


def _placeholder_allowed_in(path: Path) -> bool:
    """Restrict committed placeholders to policy-approved repository areas."""
    try:
        relative = path.resolve().relative_to(_PROJECT_ROOT)
    except ValueError:
        # Explicit external fixtures are test inputs and cannot enter a package.
        return "tests" in path.parts
    if relative == _PLACEHOLDER_POLICY.relative_to(_PROJECT_ROOT):
        return True
    return relative.parts[0] in {"docs", "samples", "tests"} or relative.parts[:2] == (
        "spec",
        "fixtures",
    )


def _scan_text(path: Path, text: str, allowed: frozenset[str]) -> list[Finding]:
    """Scan one decoded file and return findings without secret contents."""
    findings: set[tuple[int, str]] = set()
    for pattern in _PATTERNS:
        for match in pattern.expression.finditer(text):
            findings.add((_line_number(text, match.start()), pattern.name))

    for match in _SENSITIVE_ASSIGNMENT.finditer(text):
        value = match.group("value")
        if value in allowed and _placeholder_allowed_in(path):
            continue
        if re.fullmatch(r"MCONET_[A-Z0-9_]+", value):
            continue
        findings.add((_line_number(text, match.start()), "sensitive-assignment"))

    return [
        Finding(path=path, line=line, pattern=pattern)
        for line, pattern in sorted(findings)
    ]


def _scan_files(paths: Iterable[Path], allowed: frozenset[str]) -> list[Finding]:
    """Scan readable UTF-8 text files and skip binary content deterministically."""
    findings: list[Finding] = []
    for path in paths:
        try:
            content = path.read_bytes()
        except OSError as error:
            raise SecretScanError(f"Cannot read {path}: {error}") from error
        if b"\0" in content:
            continue
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            continue
        findings.extend(_scan_text(path, text, allowed))
    return findings


def _display_path(path: Path) -> str:
    """Prefer repository-relative diagnostics while supporting external fixtures."""
    try:
        return path.relative_to(_PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path)


def main(argv: Sequence[str] | None = None) -> int:
    """Return failure when any scanned text file contains a credential pattern."""
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="*", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        allowed = _load_allowed_placeholders()
        paths = _explicit_files(args.paths) if args.paths else _repository_files()
        findings = _scan_files(paths, allowed)
    except SecretScanError as error:
        print(f"Secret scan failed: {error}")
        return 2

    if findings:
        print("Potential secrets detected:")
        for finding in findings:
            print(f"- {_display_path(finding.path)}:{finding.line}: {finding.pattern}")
        return 1

    print(f"Secret scan passed for {len(paths)} files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
