"""Behavior tests for ``everydollar-reader status``.

These tests exercise the public CLI (``main``) against a temporary data
directory. They write small synthetic snapshot files directly so ``status``
can be verified without depending on ``import`` (issue #4). All snapshot
contents are invented; no real export data is used.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from everydollar_reader.cli import main


def _write_snapshot(
    data_dir: Path, month: str, snapshot_time: str
) -> Path:
    """Write a minimal synthetic snapshot for ``month`` under ``data_dir``."""
    path = data_dir / f"{month}.json"
    path.write_text(
        json.dumps(
            {"month": month, "snapshot_time": snapshot_time},
        ),
        encoding="utf-8",
    )
    return path


def test_status_lists_a_retained_month_with_its_snapshot_time(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_snapshot(data_dir, "2026-07", "2026-07-26T14:03:00+00:00")

    assert main(["--data-dir", str(data_dir), "status"]) == 0
    out = capsys.readouterr().out
    assert "2026-07" in out
    assert "2026-07-26" in out
    assert "14:03" in out


def test_status_lists_multiple_months_in_ascending_order(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_snapshot(data_dir, "2026-07", "2026-07-26T14:03:00+00:00")
    _write_snapshot(data_dir, "2026-05", "2026-05-12T09:10:00+00:00")

    assert main(["--data-dir", str(data_dir), "status"]) == 0
    out = capsys.readouterr().out
    lines = [ln for ln in out.splitlines() if ln.startswith("  ")]
    months = [ln.split()[0] for ln in lines]
    assert months == ["2026-05", "2026-07"]


def test_status_renders_snapshot_time_readable_and_flags_freshness(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_snapshot(data_dir, "2026-07", "2026-07-26T14:03:00+00:00")

    assert main(["--data-dir", str(data_dir), "status"]) == 0
    out = capsys.readouterr().out
    # ISO ``T`` separator is rendered as a readable space.
    assert "2026-07-26 14:03" in out
    assert "T14:03" not in out
    # Freshness is surfaced so a reader knows the data is point-in-time.
    assert "point-in-time" in out


def test_status_warns_on_unreadable_files_but_still_lists_valid_months(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_snapshot(data_dir, "2026-07", "2026-07-26T14:03:00+00:00")
    # A snapshot that lost its snapshot_time (corrupted cache).
    (data_dir / "2026-05.json").write_text(
        json.dumps({"month": "2026-05"}), encoding="utf-8"
    )
    # A file with a broken JSON payload.
    (data_dir / "2026-03.json").write_text("{not json", encoding="utf-8")
    # A non-snapshot file the reader must ignore entirely.
    (data_dir / "README.txt").write_text("ignore me", encoding="utf-8")

    assert main(["--data-dir", str(data_dir), "status"]) == 0
    out = capsys.readouterr().out
    listed = [ln.split()[0] for ln in out.splitlines() if ln.startswith("  ")]
    assert listed == ["2026-07"]  # only the valid month is listed
    assert "warning" in out  # corruption surfaced, not silently swallowed
    assert "README" not in out  # foreign file ignored, not warned