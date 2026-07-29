---
name: obsidian-health-check
description: "Read-only Obsidian Vault link-integrity auditor: scan broken Wikilinks, missing Markdown targets, embeds and attachments, ambiguous links, missing headings or block IDs, duplicate basenames, and produce JSON and Markdown health reports. 只读审计 Obsidian Vault 链接完整性：扫描失效 Wikilink、缺失 Markdown 目标、内嵌与附件、歧义链接、缺失标题或块 ID、重名基名，并生成 JSON 与 Markdown 健康报告。该技能绝不修改、修复、重命名、移动或重写 Vault 中的任何文件，报告目录必须位于 Vault 之外。"
---

# Obsidian Health Check

Audit an Obsidian Vault without automatic repair.

## Requirements

- Python 3.10 or newer
- PyYAML 6.x
- A report directory outside the Vault

## Run

```shell
python "$HOME/.codex/skills/obsidian-health-check/scripts/obsidian_health.py" --vault "<VAULT_PATH>" --report-dir "<REPORT_DIR>"
```

Use `config/config.local.yaml` only for private local values. CLI values override environment variables, which override local configuration.

## Safety Contract

The command resolves paths before creating report directories, rejects report destinations inside the Vault, snapshots the Vault before scanning, writes reports outside the Vault, and compares a final snapshot. It audits only and does not repair, rename, move, or rewrite Vault content.

## Exit Codes

- `0`: scan completed without ERROR/WARN
- `1`: link-integrity issues found
- `2`: invalid argument
- `3`: runtime integrity check failed
- `4`: Vault not found
- `5`: configuration error
- `6`: safety policy violation
- `7`: report path inside Vault
- `8`: Vault mutation detected

Review both generated JSON and Markdown reports. Do not claim orphan analysis, frontmatter validation, tag checks, Canvas/Bases validation, sync analysis, duplicate-content detection, or automatic repair.
