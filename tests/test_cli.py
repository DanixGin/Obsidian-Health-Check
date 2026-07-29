from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

import scripts.obsidian_health as app


def run(vault: Path, reports: Path, *extra: str) -> int:
    return app.main(["--vault", str(vault), "--report-dir", str(reports), *extra])


def snapshot(root: Path) -> tuple[tuple[str, ...], tuple[str, ...], dict[str, str]]:
    directories = tuple(
        sorted(path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_dir())
    )
    files = tuple(
        sorted(path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file())
    )
    hashes = {rel: hashlib.sha256((root / rel).read_bytes()).hexdigest() for rel in files}
    return directories, files, hashes


def test_cli_accepts_report_dir_outside_vault(vault: Path, tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    assert run(vault, reports) == app.ExitCode.ISSUES_FOUND
    assert len(list(reports.glob("*.json"))) == 1
    assert len(list(reports.glob("*.md"))) == 1


def test_cli_rejects_report_dir_equal_to_vault(vault: Path) -> None:
    assert run(vault, vault) == app.ExitCode.REPORT_PATH_INSIDE_VAULT


def test_cli_rejects_report_dir_inside_vault(vault: Path) -> None:
    assert run(vault, vault / "reports") == app.ExitCode.REPORT_PATH_INSIDE_VAULT
    assert not (vault / "reports").exists()


def test_cli_rejects_parent_traversal_into_vault(vault: Path) -> None:
    path = vault.parent / "outside" / ".." / vault.name / "reports"
    assert run(vault, path) == app.ExitCode.REPORT_PATH_INSIDE_VAULT


def test_cli_rejects_symlink_into_vault(vault: Path, tmp_path: Path) -> None:
    link = tmp_path / "link"
    try:
        link.symlink_to(vault, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"Directory symlink unavailable: {error}")
    assert run(vault, link / "reports") == app.ExitCode.REPORT_PATH_INSIDE_VAULT


def test_cli_does_not_modify_vault(vault: Path, tmp_path: Path) -> None:
    before = snapshot(vault)
    run(vault, tmp_path / "reports")
    assert snapshot(vault) == before
    assert (vault / ".obsidian" / "app.json").read_text(encoding="utf-8").splitlines() == ["{}"]


def test_cli_uses_single_utc_timestamp(vault: Path, tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    run(vault, reports)
    json_path = next(reports.glob("*.json"))
    markdown_path = next(reports.glob("*.md"))
    match = re.search(r"(\d{8}T\d{6}Z)", json_path.name)
    assert match
    stamp = match.group(1)
    assert stamp in markdown_path.name
    report = json.loads(json_path.read_text(encoding="utf-8"))
    assert report["timestamp"].endswith("Z")
    assert report["timestamp"].replace("-", "").replace(":", "")[:15] + "Z" == stamp
    assert report["timestamp"] in markdown_path.read_text(encoding="utf-8")


def test_cli_exit_codes_match_contract(vault: Path, tmp_path: Path) -> None:
    assert run(vault, tmp_path / "issues") == app.ExitCode.ISSUES_FOUND
    clean = tmp_path / "clean"
    clean.mkdir()
    (clean / "ok.md").write_text("# OK" + chr(10), encoding="utf-8")
    assert run(clean, tmp_path / "clean-report") == app.ExitCode.SCAN_OK
    assert (
        app.main(["--vault", str(tmp_path / "missing"), "--report-dir", str(tmp_path / "r")])
        == app.ExitCode.VAULT_NOT_FOUND
    )
    assert app.main([]) == app.ExitCode.INVALID_ARGUMENT
    assert [int(code) for code in app.ExitCode] == list(range(9))


def test_placeholder_config_is_rejected(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text(
        chr(10).join(
            ["vault: REPLACE_ME_WITH_VAULT", "report_dir: REPLACE_ME_WITH_REPORT_DIR", ""]
        ),
        encoding="utf-8",
    )
    assert app.main(["--config", str(config)]) == app.ExitCode.CONFIG_ERROR


def test_config_precedence(vault: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = tmp_path / "config.yaml"
    config_report, env_report, cli_report = (
        tmp_path / "config-report",
        tmp_path / "env-report",
        tmp_path / "cli-report",
    )
    config.write_text(
        chr(10).join(
            [
                f"vault: {vault.as_posix()}",
                f"report_dir: {config_report.as_posix()}",
                "strict_readonly: true",
                "",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("OBSIDIAN_HEALTH_REPORT_DIR", str(env_report))
    assert (
        app.main(["--config", str(config), "--report-dir", str(cli_report)])
        == app.ExitCode.ISSUES_FOUND
    )
    assert (
        list(cli_report.glob("*.json")) and not env_report.exists() and not config_report.exists()
    )


def test_environment_precedes_config(
    vault: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "config.yaml"
    config_report, env_report = tmp_path / "config-report", tmp_path / "env-report"
    config.write_text(
        chr(10).join([f"vault: {vault.as_posix()}", f"report_dir: {config_report.as_posix()}", ""]),
        encoding="utf-8",
    )
    monkeypatch.setenv("OBSIDIAN_HEALTH_REPORT_DIR", str(env_report))
    assert app.main(["--config", str(config)]) == app.ExitCode.ISSUES_FOUND
    assert list(env_report.glob("*.json")) and not config_report.exists()


def test_strict_readonly_false_is_rejected(vault: Path, tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text("strict_readonly: false" + chr(10), encoding="utf-8")
    assert (
        app.main(
            ["--config", str(config), "--vault", str(vault), "--report-dir", str(tmp_path / "r")]
        )
        == app.ExitCode.SAFETY_POLICY_VIOLATION
    )


def test_config_parse_failure_is_distinct(tmp_path: Path) -> None:
    config = tmp_path / "bad.yaml"
    config.write_text("[invalid", encoding="utf-8")
    assert app.main(["--config", str(config)]) == app.ExitCode.CONFIG_ERROR
