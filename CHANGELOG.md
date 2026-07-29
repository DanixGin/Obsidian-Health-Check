# Changelog

All notable changes are documented here.

## [1.0.1] - 2026-07-29

### Changed

- Rebuilt the public CLI, documentation, tests, packaging, and Codex Skill metadata.
- Defined stable exit codes and one UTC timestamp per report pair.

### Security

- Reject report paths that resolve to the Vault or any location inside it.
- Verify full Vault and `.obsidian` snapshots after report creation.

## [1.0.0] - 2026-07-28

- Initial public baseline.
