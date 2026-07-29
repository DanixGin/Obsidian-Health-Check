# Checks

Obsidian Health Check v1.0.1 audits these link-integrity conditions:

- broken Wikilinks and missing Markdown link targets;
- missing embeds and attachment targets;
- ambiguous short links that match multiple basenames;
- missing headings and block IDs;
- duplicate basenames across the Vault.

The scanner skips dot-prefixed directories, including `.obsidian`, while the safety snapshot still hashes `.obsidian` so unexpected changes are detected.
