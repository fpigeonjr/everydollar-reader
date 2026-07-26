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
            "--budget",
            str(tmp_path / "missing-budget.csv"),
            "--transactions",
            str(tmp_path / "missing-tx.csv"),
        ]
    )
    assert code == 2
    err = capsys.readouterr().err
    assert "not found" in err


def test_import_schema_gate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    budget = tmp_path / "budget.csv"
    tx = tmp_path / "tx.csv"
    budget.write_text("header\n", encoding="utf-8")
    tx.write_text("header\n", encoding="utf-8")

    code = main(
        [
            "--data-dir",
            str(tmp_path / "data"),
            "import",
            "--budget",
            str(budget),
            "--transactions",
            str(tx),
        ]
    )
    assert code == 1
    err = capsys.readouterr().err
    assert "schema discovery" in err


def test_item_schema_gate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["--data-dir", str(tmp_path), "item", "Dining"])
    assert code == 1
    err = capsys.readouterr().err
    assert "Dining" in err
    assert "schema discovery" in err
