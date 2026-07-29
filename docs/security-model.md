# Security Model

The CLI resolves the Vault and report paths before creating the report directory. It rejects a report directory equal to or inside the Vault, including resolved `..` traversal and symlink destinations.

A pre-scan snapshot records directory paths, file paths, SHA-256 hashes, sizes, and `.obsidian` state. Reports are written outside the Vault, then a final snapshot is compared. If the snapshots differ, generated reports are discarded and exit code `8` is returned.

This is a detection boundary, not filesystem sandboxing. Concurrent applications may legitimately change a Vault during a scan; that run will fail closed.
