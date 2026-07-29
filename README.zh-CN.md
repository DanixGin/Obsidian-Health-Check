# Obsidian Health Check

只读 Obsidian Vault 链接完整性审计工具与 Codex Skill。

它可以报告损坏的 Wikilink、缺失的 Markdown 目标、缺失的嵌入文件和附件、有歧义的短链接、缺失的标题、缺失的块 ID，以及重复的文件基本名。

它目前不执行孤立笔记分析、frontmatter schema 验证、标签检查、Canvas/Bases 检查、同步冲突分析、重复内容检测或自动修复。

CLI 不会主动向 Vault 写入任何内容。程序会解析并拒绝位于 Vault 内部的报告路径，在扫描前记录文件和目录状态，将报告写入 Vault 外部，并在全部操作完成后验证最终 Vault 快照。详细说明见[安全模型](docs/security-model.md)。

[English](README.md)

## 快速开始

```shell
python -m pip install -e .
python scripts/obsidian_health.py --vault "<VAULT_PATH>" --report-dir "<REPORT_DIR>"
```

安装后的命令行入口：

```shell
obsidian-health-check --vault "<VAULT_PATH>" --report-dir "<REPORT_DIR>"
```

JSON 和 Markdown 报告使用同一个 UTC 时间戳，文件名格式为：

```text
obsidian-health_YYYYMMDDTHHMMSSZ.json
obsidian-health_YYYYMMDDTHHMMSSZ.md
```

## 配置

将：

```text
config/config.example.yaml
```

复制为：

```text
config/config.local.yaml
```

然后替换其中的占位符。

配置解析优先级为：

```text
CLI > 环境变量 > config.local.yaml > 安全的项目默认值
```

支持的环境变量：

```text
OBSIDIAN_HEALTH_VAULT
OBSIDIAN_HEALTH_REPORT_DIR
```

仍包含占位符的配置会被拒绝执行。

## 退出码

| 代码 | 名称 | 含义 |
|-:|---|---|
|  0 | `SCAN_OK` | 扫描完成，未发现 ERROR 或 WARN |
|  1 | `ISSUES_FOUND` | 发现链接完整性问题 |
|  2 | `INVALID_ARGUMENT` | 必需参数缺失或参数无效 |
|  3 | `INTEGRITY_CHECK_FAILED` | 运行期 I/O 或完整性检查失败 |
|  4 | `VAULT_NOT_FOUND` | Vault 目录不存在 |
|  5 | `CONFIG_ERROR` | 配置缺失、无效或仍包含占位符 |
|  6 | `SAFETY_POLICY_VIOLATION` | 只读安全策略被禁用 |
|  7 | `REPORT_PATH_INSIDE_VAULT` | 报告路径解析后等于 Vault 或位于 Vault 内 |
|  8 | `VAULT_MUTATION_DETECTED` | 审计过程中检测到 Vault 发生变化 |

## 开发验证

```shell
python -m pip install -e ".[dev]"
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
python -m mypy scripts
python -m build
```

更多信息：

* [检查项目](docs/checks.md)
* [已知限制](docs/limitations.md)
* [安全模型](docs/security-model.md)

MIT 许可。
