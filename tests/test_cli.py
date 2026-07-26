"""Smoke tests for the CLI skeleton."""

from __future__ import annotations

from pathlib import Path

import pytest

from everydollar_reader.cli import main
from everydollar_reader.paths import data_home


def test_help_lists_first_cut_commands(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "import" in out
    assert "status" in out
    assert "item" in out


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert "0.1.0" in capsys.readouterr().out


def test_status_empty_cache(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert main(["status"]) == 0
    out = capsys.readouterr().out
    assert str(tmp_path / "everydollar-reader") in out
    assert "No budget snapshots imported yet." in out


def test_data_home_respects_xdg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert data_home() == tmp_path / "everydollar-reader"


def test_data_home_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setattr(
        "everydollar_reader.paths.Path.home",
        lambda: Path("/tmp/fake-home"),
    )
    assert data_home() == Path("/tmp/fake-home/.local/share/everydollar-reader")


def test_import_missing_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(
        [
            "--data-dir",
            str(tmp_path),
            "import",
            "--month",
            "2026-07",
            "--budget",
            str(tmp_path / "missing-budget.csv"),
            "--transactions",
            str(tmp_path / "missing-tx.csv"),
        ]
    )
    assert code == 2
    err = capsys.readouterr().err
    assert "not found" in err


def test_import_maltered_headers_fail_without_writing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    budget = tmp_path / "budget.csv"
    tx = tmp_path / "tx.csv"
    budget.write_text("header\n", encoding="utf-8")
    tx.write_text("header\n", encoding="utf-8")
    data_dir = tmp_path / "data"

    code = main(
        [
            "--data-dir",
            str(data_dir),
            "import",
            "--month",
            "2026-07",
            "--budget",
            str(budget),
            "--transactions",
            str(tx),
        ]
    )
    assert code != 0
    err = capsys.readouterr().err
    # Structural-only error; no snapshot file should be written.
    assert "headers" in err
    assert not (data_dir / "2026-07.json").is_file()


def test_item_no_snapshots_reports_empty_not_gated(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # ``item`` no longer emits the schema-discovery gate; with no snapshots
    # it reports the empty cache readably (exit 0) rather than erroring.
    code = main(["--data-dir", str(tmp_path), "item", "Dining"])
    assert code == 0
    out = capsys.readouterr().out
    assert "No budget snapshots imported yet." in out
    assert "schema discovery" not in out
