# Obsidian Health Check

Timestamp: `2026-07-29T12:41:09.269761Z`
Vault: `sample_vault`
Vault modified: `false`

## Summary

- ERROR: 2
- WARN: 3
- INFO: 1

## Issues

### INFO - duplicate_basename

- Location: `Vault`
- Target: `shared.md`
- Rationale: Multiple files share this basename.

### WARN - ambiguous_link

- Location: `ambiguous.md:1`
- Target: `shared`
- Rationale: The short link resolves to multiple files.

### ERROR - missing_target

- Location: `broken.md:1`
- Target: `missing-note`
- Rationale: No matching Vault target was found.

### ERROR - missing_embed

- Location: `broken.md:2`
- Target: `missing.png`
- Rationale: No matching Vault target was found.

### WARN - missing_heading

- Location: `broken.md:3`
- Target: `folder/nested`
- Rationale: The target note does not contain this heading.

### WARN - missing_block

- Location: `broken.md:4`
- Target: `block-note`
- Rationale: The target note does not contain this block ID.
