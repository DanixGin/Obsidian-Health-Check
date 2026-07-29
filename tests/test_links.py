from __future__ import annotations

from pathlib import Path

import pytest

from scripts.obsidian_health import VaultIndex, audit, iter_links, parse_target


def index(vault: Path) -> VaultIndex:
    value = VaultIndex(vault, [".md"], [".png", ".pdf"])
    value.scan()
    return value


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("note", ("note", None, None)),
        ("note|Alias", ("note", None, None)),
        ("note#Heading", ("note", "Heading", None)),
        ("note#^block-id", ("note", None, "block-id")),
    ],
)
def test_parse_target(raw: str, expected: tuple[str, str | None, str | None]) -> None:
    assert parse_target(raw) == expected


def test_iter_links_skips_fenced_and_inline_code() -> None:
    content = """```
[[bad]]
```
`[[bad2]]` [[good]]"""
    links = list(iter_links(content))
    assert [item[2] for item in links] == ["good"]


def test_iter_links_supports_wikilinks_markdown_and_embeds() -> None:
    links = list(iter_links("[[note]] [x](folder/nested.md) ![[assets/image.png]]"))
    assert [(item[2], item[3]) for item in links] == [
        ("note", False),
        ("assets/image.png", True),
        ("folder/nested.md", False),
    ]


def test_index_skips_dot_directories_and_indexes_structure(vault: Path) -> None:
    value = index(vault)
    assert ".obsidian/app.json" not in value.files
    assert "known heading" in value.headings["folder/nested.md"]
    assert "valid-block" in value.blocks["block-note.md"]


def test_audit_detects_supported_issue_categories(vault: Path) -> None:
    issues = audit(index(vault))
    categories = {issue.category for issue in issues}
    assert {
        "missing_target",
        "missing_embed",
        "ambiguous_link",
        "missing_heading",
        "missing_block",
        "duplicate_basename",
    } <= categories


def test_source_relative_path_has_precedence(vault: Path) -> None:
    value = index(vault)
    assert value.resolve("index.md", "folder/nested", False) == ["folder/nested.md"]


def test_duplicate_short_name_is_ambiguous(vault: Path) -> None:
    value = index(vault)
    assert value.resolve("ambiguous.md", "shared", False) == ["a/shared.md", "b/shared.md"]
