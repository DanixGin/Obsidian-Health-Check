# Obsidian Health Check

A read-only Obsidian Vault link-integrity auditor and Codex Skill.

It reports broken Wikilinks, missing Markdown targets, missing embeds and attachments, ambiguous short links, missing headings, missing block IDs, and duplicate basenames. It does not perform orphan analysis, frontmatter validation, tag or Canvas/Bases checks, sync analysis, duplicate-content detection, or automatic repair.

The CLI never intentionally writes to the Vault. It resolves and rejects report paths inside the Vault, snapshots file and directory state before scanning, writes reports outside the Vault, and verifies the final Vault snapshot. See [Security Model](docs/security-model.md).

[中文文档](README.zh-CN.md)

## Quick Start

```shell
python -m pip install -e .
python scripts/obsidian_health.py --vault "<VAULT_PATH>" --report-dir "<REPORT_DIR>"
```

Installed entry point:

```shell
obsidian-health-check --vault "<VAULT_PATH>" --report-dir "<REPORT_DIR>"
```

Reports are named `obsidian-health_YYYYMMDDTHHMMSSZ.json` and `.md` using one UTC timestamp.

## Configuration

Copy `config/config.example.yaml` to `config/config.local.yaml` and replace the placeholders. Resolution order is:

```text
CLI > environment variable > config.local.yaml > safe project default
```

Environment variables are `OBSIDIAN_HEALTH_VAULT` and `OBSIDIAN_HEALTH_REPORT_DIR`. Placeholder values are rejected.

## Exit Codes

| Code | Name | Meaning |
|---:|---|---|
| 0 | `SCAN_OK` | Scan completed without ERROR or WARN findings |
| 1 | `ISSUES_FOUND` | Link-integrity issues were found |
| 2 | `INVALID_ARGUMENT` | Required argument is missing or invalid |
| 3 | `INTEGRITY_CHECK_FAILED` | Runtime I/O or integrity operation failed |
| 4 | `VAULT_NOT_FOUND` | Vault directory does not exist |
| 5 | `CONFIG_ERROR` | Configuration is missing, invalid, or still contains placeholders |
| 6 | `SAFETY_POLICY_VIOLATION` | Read-only safety policy is disabled |
| 7 | `REPORT_PATH_INSIDE_VAULT` | Report path resolves to the Vault or inside it |
| 8 | `VAULT_MUTATION_DETECTED` | Vault changed during the audit |

## Development

```shell
python -m pip install -e ".[dev]"
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
python -m mypy scripts
python -m build
```

See [Checks](docs/checks.md) and [Limitations](docs/limitations.md). Licensed under MIT.
