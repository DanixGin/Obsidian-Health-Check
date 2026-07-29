#!/usr/bin/env python3
"""Read-only Obsidian Vault link-integrity auditor."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections import defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import IntEnum
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import yaml

VERSION = "1.0.1"
PLACEHOLDERS = ("REPLACE_ME", "<VAULT_PATH>", "<REPORT_DIR>")
DEFAULT_CONFIG = Path("config/config.local.yaml")
DEFAULT_REPORT_DIR = Path.home() / ".local" / "state" / "obsidian-health-check"
DEFAULT_MD_EXTENSIONS = [".md"]
DEFAULT_ATTACHMENT_EXTENSIONS = [
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".svg",
    ".pdf",
    ".txt",
    ".mp3",
    ".wav",
    ".mp4",
    ".mov",
    ".zip",
]


class ExitCode(IntEnum):
    SCAN_OK = 0
    ISSUES_FOUND = 1
    INVALID_ARGUMENT = 2
    INTEGRITY_CHECK_FAILED = 3
    VAULT_NOT_FOUND = 4
    CONFIG_ERROR = 5
    SAFETY_POLICY_VIOLATION = 6
    REPORT_PATH_INSIDE_VAULT = 7
    VAULT_MUTATION_DETECTED = 8


@dataclass(frozen=True)
class Issue:
    severity: str
    category: str
    file: str
    line: int
    original: str
    target: str
    rationale: str
    candidates: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class VaultSnapshot:
    directories: tuple[str, ...]
    files: tuple[str, ...]
    hashes: tuple[tuple[str, str], ...]
    sizes: tuple[tuple[str, int], ...]
    obsidian: tuple[tuple[str, str, int], ...]


class CliError(Exception):
    def __init__(self, message: str, exit_code: ExitCode) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def resolved(path: Path) -> Path:
    return Path(os.path.expandvars(str(path))).expanduser().resolve(strict=False)


def is_same_or_child(path: Path, parent: Path) -> bool:
    try:
        common = os.path.commonpath((os.path.normcase(str(path)), os.path.normcase(str(parent))))
    except ValueError:
        return False
    return common == os.path.normcase(str(parent))


def validate_report_directory(vault_root: Path, report_dir: Path) -> tuple[Path, Path]:
    vault = resolved(vault_root)
    report = resolved(report_dir)
    if is_same_or_child(report, vault):
        raise CliError(
            f"Report directory must be outside the Vault: {report}",
            ExitCode.REPORT_PATH_INSIDE_VAULT,
        )
    return vault, report


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot_vault(root: Path) -> VaultSnapshot:
    directories: list[str] = []
    files: list[str] = []
    hashes: list[tuple[str, str]] = []
    sizes: list[tuple[str, int]] = []
    obsidian: list[tuple[str, str, int]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix().casefold()):
        rel = path.relative_to(root).as_posix()
        if path.is_dir():
            directories.append(rel)
        elif path.is_file():
            digest, size = sha256(path), path.stat().st_size
            files.append(rel)
            hashes.append((rel, digest))
            sizes.append((rel, size))
            if rel == ".obsidian" or rel.startswith(".obsidian/"):
                obsidian.append((rel, digest, size))
    return VaultSnapshot(
        tuple(directories), tuple(files), tuple(hashes), tuple(sizes), tuple(obsidian)
    )


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8-sig")


def strip_code(content: str) -> str:
    output: list[str] = []
    in_fence = False
    for line in content.splitlines(keepends=True):
        if line.lstrip().startswith(("```", "~~~")):
            in_fence = not in_fence
            output.append("\n" if line.endswith("\n") else "")
        elif in_fence:
            output.append("\n" if line.endswith("\n") else "")
        else:
            output.append(re.sub(r"`[^`\n]*`", "", line))
    return "".join(output)


WIKILINK_RE = re.compile(r"(!?)\[\[([^\]]*)\]\]")
MARKDOWN_LINK_RE = re.compile(r"(!?)\[[^\]]*\]\(([^)]+)\)")


def parse_target(raw: str) -> tuple[str, str | None, str | None]:
    target = unquote(raw.strip().split("|", 1)[0].strip())
    block = heading = None
    if "#^" in target:
        target, block = target.split("#^", 1)
    elif "#" in target:
        target, heading = target.split("#", 1)
    return target.strip(), heading, block


def normalize_heading(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


class VaultIndex:
    def __init__(self, root: Path, md_exts: Iterable[str], attachment_exts: Iterable[str]) -> None:
        self.root = root
        self.md_exts = {item.casefold() for item in md_exts}
        self.attachment_exts = {item.casefold() for item in attachment_exts}
        self.files: dict[str, Path] = {}
        self.by_basename: dict[str, list[str]] = defaultdict(list)
        self.headings: dict[str, set[str]] = defaultdict(set)
        self.blocks: dict[str, set[str]] = defaultdict(set)

    def scan(self) -> None:
        for path in self.root.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(self.root).as_posix()
            if any(part.startswith(".") for part in Path(rel).parts):
                continue
            self.files[rel] = path
            self.by_basename[path.name.casefold()].append(rel)
            if path.suffix.casefold() in self.md_exts:
                self._index_markdown(rel, path)

    def _index_markdown(self, rel: str, path: Path) -> None:
        for line in strip_code(read_text(path)).splitlines():
            heading = re.match(r"^#{1,6}\s+(.+?)\s*$", line)
            if heading:
                value = re.sub(r"\s+\^[A-Za-z0-9_-]+\s*$", "", heading.group(1))
                self.headings[rel].add(normalize_heading(value))
            block = re.search(r"(?:^|\s)\^([A-Za-z0-9_-]+)\s*$", line)
            if block:
                self.blocks[rel].add(block.group(1))

    def markdown_files(self) -> Iterator[tuple[str, Path]]:
        for rel, path in self.files.items():
            if path.suffix.casefold() in self.md_exts:
                yield rel, path

    def resolve(self, source: str, target: str, is_embed: bool) -> list[str]:
        clean = target.replace("\\", "/").lstrip("/")
        suffix = Path(clean).suffix.casefold()
        names = [clean] if suffix else [f"{clean}.md"]
        candidates: list[str] = []
        for name in names:
            source_relative = (Path(source).parent / name).as_posix()
            for candidate in (source_relative, name):
                if candidate in self.files and candidate not in candidates:
                    candidates.append(candidate)
        basename = Path(clean).name
        lookups = [basename] if suffix else [f"{basename}.md"]
        if is_embed and not suffix:
            lookups.extend(
                name
                for name in self.by_basename
                if Path(name).stem.casefold() == basename.casefold()
            )
        for name in lookups:
            for candidate in self.by_basename.get(name.casefold(), []):
                if candidate not in candidates:
                    candidates.append(candidate)
        return candidates


def iter_links(content: str) -> Iterator[tuple[int, str, str, bool]]:
    for number, line in enumerate(strip_code(content).splitlines(), 1):
        for match in WIKILINK_RE.finditer(line):
            yield number, match.group(0), match.group(2), bool(match.group(1))
        for match in MARKDOWN_LINK_RE.finditer(line):
            raw = match.group(2).strip().split(maxsplit=1)[0].strip("<>")
            if not re.match(r"^(?:https?:|mailto:|data:|#)", raw, re.IGNORECASE):
                yield number, match.group(0), raw, bool(match.group(1))


def audit(index: VaultIndex) -> list[Issue]:
    issues: list[Issue] = []
    for basename, candidates in sorted(index.by_basename.items()):
        if len(candidates) > 1:
            issues.append(
                Issue(
                    "INFO",
                    "duplicate_basename",
                    "",
                    0,
                    basename,
                    basename,
                    "Multiple files share this basename.",
                    candidates,
                )
            )
    for source, path in sorted(index.markdown_files()):
        for line, original, raw, is_embed in iter_links(read_text(path)):
            target, heading, block = parse_target(raw)
            if not target:
                target = source
            candidates = [source] if target == source else index.resolve(source, target, is_embed)
            if not candidates:
                category = "missing_embed" if is_embed else "missing_target"
                issues.append(
                    Issue(
                        "ERROR",
                        category,
                        source,
                        line,
                        original,
                        target,
                        "No matching Vault target was found.",
                    )
                )
                continue
            if len(candidates) > 1:
                issues.append(
                    Issue(
                        "WARN",
                        "ambiguous_link",
                        source,
                        line,
                        original,
                        target,
                        "The short link resolves to multiple files.",
                        candidates,
                    )
                )
                continue
            resolved_target = candidates[0]
            if heading and normalize_heading(heading) not in index.headings.get(
                resolved_target, set()
            ):
                issues.append(
                    Issue(
                        "WARN",
                        "missing_heading",
                        source,
                        line,
                        original,
                        target,
                        "The target note does not contain this heading.",
                        candidates,
                    )
                )
            if block and block not in index.blocks.get(resolved_target, set()):
                issues.append(
                    Issue(
                        "WARN",
                        "missing_block",
                        source,
                        line,
                        original,
                        target,
                        "The target note does not contain this block ID.",
                        candidates,
                    )
                )
    return issues


def load_config(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    if not path.exists():
        raise CliError(f"Configuration file not found: {path}", ExitCode.CONFIG_ERROR)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, UnicodeError, yaml.YAMLError) as error:
        raise CliError(f"Unable to read configuration: {error}", ExitCode.CONFIG_ERROR) from error
    if not isinstance(data, dict):
        raise CliError("Configuration root must be a mapping.", ExitCode.CONFIG_ERROR)
    return data


def configured_value(
    cli: str | None, env: str, config: dict[str, Any], key: str, default: str | None = None
) -> str | None:
    if cli is not None:
        return cli
    if os.environ.get(env):
        return os.environ[env]
    value = config.get(key, default)
    return str(value) if value is not None else None


def reject_placeholder(value: str | None, label: str) -> None:
    if value and any(marker.casefold() in value.casefold() for marker in PLACEHOLDERS):
        raise CliError(
            f"{label} contains a placeholder and must be configured.", ExitCode.CONFIG_ERROR
        )


def build_report(vault: Path, issues: list[Issue], timestamp: datetime) -> dict[str, Any]:
    counts = {
        severity: sum(issue.severity == severity for issue in issues)
        for severity in ("ERROR", "WARN", "INFO")
    }
    return {
        "tool": "obsidian-health-check",
        "version": VERSION,
        "timestamp": timestamp.isoformat().replace("+00:00", "Z"),
        "vault": vault.name,
        "summary": counts,
        "vault_modified": False,
        "issues": [asdict(issue) for issue in issues],
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Obsidian Health Check",
        "",
        f"Timestamp: `{report['timestamp']}`",
        f"Vault: `{report['vault']}`",
        f"Vault modified: `{str(report['vault_modified']).lower()}`",
        "",
        "## Summary",
        "",
        f"- ERROR: {report['summary']['ERROR']}",
        f"- WARN: {report['summary']['WARN']}",
        f"- INFO: {report['summary']['INFO']}",
        "",
        "## Issues",
        "",
    ]
    if not report["issues"]:
        lines.append("No link-integrity issues found.")
    for issue in report["issues"]:
        location = f"{issue['file']}:{issue['line']}" if issue["file"] else "Vault"
        lines.extend(
            [
                f"### {issue['severity']} - {issue['category']}",
                "",
                f"- Location: `{location}`",
                f"- Target: `{issue['target']}`",
                f"- Rationale: {issue['rationale']}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def write_reports(
    report_dir: Path, report: dict[str, Any], timestamp: datetime
) -> tuple[Path, Path]:
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = timestamp.strftime("%Y%m%dT%H%M%SZ")
    json_path = report_dir / f"obsidian-health_{stamp}.json"
    markdown_path = report_dir / f"obsidian-health_{stamp}.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    markdown_path.write_text(render_markdown(report), encoding="utf-8", newline="\n")
    return json_path, markdown_path


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only Obsidian Vault link-integrity auditor.")
    parser.add_argument("--vault", help="Path to the Obsidian Vault.")
    parser.add_argument("--report-dir", help="Directory outside the Vault for reports.")
    parser.add_argument("--config", type=Path, help="YAML configuration file.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    return parser


def run(argv: list[str] | None = None) -> ExitCode:
    args = create_parser().parse_args(argv)
    config_path = args.config or (DEFAULT_CONFIG if DEFAULT_CONFIG.exists() else None)
    config = load_config(config_path)
    if config.get("strict_readonly", True) is not True:
        raise CliError("strict_readonly must be true.", ExitCode.SAFETY_POLICY_VIOLATION)
    vault_value = configured_value(args.vault, "OBSIDIAN_HEALTH_VAULT", config, "vault")
    report_value = configured_value(
        args.report_dir, "OBSIDIAN_HEALTH_REPORT_DIR", config, "report_dir", str(DEFAULT_REPORT_DIR)
    )
    reject_placeholder(vault_value, "Vault path")
    reject_placeholder(report_value, "Report path")
    if not vault_value:
        raise CliError("A Vault path is required.", ExitCode.INVALID_ARGUMENT)
    if not report_value:
        raise CliError("A report directory is required.", ExitCode.INVALID_ARGUMENT)
    vault, report_dir = validate_report_directory(Path(vault_value), Path(report_value))
    if not vault.is_dir():
        raise CliError(f"Vault directory not found: {vault}", ExitCode.VAULT_NOT_FOUND)
    before = snapshot_vault(vault)
    index = VaultIndex(
        vault,
        config.get("markdown_extensions", DEFAULT_MD_EXTENSIONS),
        config.get("attachment_extensions", DEFAULT_ATTACHMENT_EXTENSIONS),
    )
    index.scan()
    issues = audit(index)
    timestamp = datetime.now(timezone.utc)
    report = build_report(vault, issues, timestamp)
    paths = write_reports(report_dir, report, timestamp)
    if before != snapshot_vault(vault):
        for path in paths:
            path.unlink(missing_ok=True)
        raise CliError(
            "Vault changed during the audit; reports were discarded.",
            ExitCode.VAULT_MUTATION_DETECTED,
        )
    print(f"JSON report: {paths[0]}")
    print(f"Markdown report: {paths[1]}")
    return (
        ExitCode.ISSUES_FOUND
        if any(issue.severity in {"ERROR", "WARN"} for issue in issues)
        else ExitCode.SCAN_OK
    )


def main(argv: list[str] | None = None) -> int:
    try:
        return int(run(argv))
    except CliError as error:
        print(f"error: {error}", file=sys.stderr)
        return int(error.exit_code)
    except (OSError, UnicodeError) as error:
        print(f"error: integrity check failed: {error}", file=sys.stderr)
        return int(ExitCode.INTEGRITY_CHECK_FAILED)


if __name__ == "__main__":
    raise SystemExit(main())
