from __future__ import annotations

import os
from pathlib import Path

import pytest

import scripts.obsidian_health as app


def test_report_directory_outside_vault_is_accepted(vault: Path, tmp_path: Path) -> None:
    assert (
        app.validate_report_directory(vault, tmp_path / "reports")[1]
        == (tmp_path / "reports").resolve()
    )


@pytest.mark.parametrize("relative", [".", "reports", "nested/reports"])
def test_report_directory_same_or_inside_vault_is_rejected(vault: Path, relative: str) -> None:
    with pytest.raises(app.CliError) as caught:
        app.validate_report_directory(vault, vault / relative)
    assert caught.value.exit_code == app.ExitCode.REPORT_PATH_INSIDE_VAULT


def test_parent_traversal_into_vault_is_rejected(vault: Path) -> None:
    candidate = vault.parent / "outside" / ".." / vault.name / "reports"
    with pytest.raises(app.CliError):
        app.validate_report_directory(vault, candidate)


def test_symlink_into_vault_is_rejected(vault: Path, tmp_path: Path) -> None:
    link = tmp_path / "vault-link"
    try:
        link.symlink_to(vault, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"Directory symlink unavailable: {error}")
    with pytest.raises(app.CliError):
        app.validate_report_directory(vault, link / "reports")


def test_snapshot_tracks_files_directories_hashes_and_obsidian(vault: Path) -> None:
    snapshot = app.snapshot_vault(vault)
    assert "a" in snapshot.directories and "note.md" in snapshot.files
    assert dict(snapshot.hashes)["note.md"]
    assert dict(snapshot.sizes)["note.md"] > 0
    assert snapshot.obsidian and snapshot.obsidian[0][0] == ".obsidian/app.json"


def test_cli_detects_unexpected_vault_mutation(
    vault: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = app.write_reports

    def mutating_write(report_dir: Path, report: dict[str, object], timestamp: object):
        paths = original(report_dir, report, timestamp)  # type: ignore[arg-type]
        (vault / "unexpected.md").write_text("changed", encoding="utf-8")
        return paths

    monkeypatch.setattr(app, "write_reports", mutating_write)
    assert (
        app.main(["--vault", str(vault), "--report-dir", str(tmp_path / "reports")])
        == app.ExitCode.VAULT_MUTATION_DETECTED
    )
    assert not list((tmp_path / "reports").glob("obsidian-health_*"))


def test_windows_case_normalization_contract() -> None:
    if os.name != "nt":
        pytest.skip("Windows-only path comparison")
    assert app.is_same_or_child(Path("C:/VAULT/reports"), Path("c:/vault"))
