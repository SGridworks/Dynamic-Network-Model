"""Smoke + state tests for the `hermes autoresearch` CLI subcommands."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from hermes.autoresearch.commit import (
    KillSwitchState,
    load_killswitch,
    save_killswitch,
)
from hermes.cli import app

runner = CliRunner()


def test_status_on_missing_state_reports_not_halted(tmp_path: Path) -> None:
    ks = tmp_path / "ks.json"
    ledger = tmp_path / "ledger.json"
    result = runner.invoke(
        app,
        ["autoresearch", "status", "--killswitch-path", str(ks), "--ledger-path", str(ledger)],
    )
    assert result.exit_code == 0
    assert "halted: False" in result.output
    assert "consecutive_regressions: 0" in result.output
    assert "no ledger" in result.output


def test_status_shows_ledger_entries(tmp_path: Path) -> None:
    ks = tmp_path / "ks.json"
    ledger = tmp_path / "ledger.json"
    ledger.write_text(
        json.dumps(
            [
                {
                    "iteration_id": "20260421-103000-abc",
                    "substation_id": "SUB-001",
                    "timestamp": "2026-04-21T10:30:00+00:00",
                    "decision": "accept",
                    "commit_kind": "minor_auto_commit",
                    "target_axis": "brevity",
                    "commit_sha": "abc1234",
                }
            ]
        )
    )
    result = runner.invoke(
        app,
        ["autoresearch", "status", "--killswitch-path", str(ks), "--ledger-path", str(ledger)],
    )
    assert result.exit_code == 0
    assert "SUB-001" in result.output
    # Rich may truncate wide cells with an ellipsis in a narrow terminal; check
    # the prefix so the assertion survives truncation.
    assert "minor_auto" in result.output
    assert "brevity" in result.output


def test_halt_writes_halted_state(tmp_path: Path) -> None:
    ks = tmp_path / "ks.json"
    result = runner.invoke(
        app,
        ["autoresearch", "halt", "--killswitch-path", str(ks), "--reason", "investigating drift"],
    )
    assert result.exit_code == 0
    assert "HALTED" in result.output
    state = load_killswitch(ks)
    assert state.halted is True
    assert "investigating drift" in (state.last_run_ts or "")


def test_unhalt_resets_state(tmp_path: Path) -> None:
    ks = tmp_path / "ks.json"
    save_killswitch(
        KillSwitchState(consecutive_regressions=3, halted=True, last_run_ts="t"),
        ks,
    )
    result = runner.invoke(app, ["autoresearch", "unhalt", "--killswitch-path", str(ks)])
    assert result.exit_code == 0
    assert "UNHALTED" in result.output
    state = load_killswitch(ks)
    assert state.halted is False
    assert state.consecutive_regressions == 0


def test_status_after_halt_shows_halted(tmp_path: Path) -> None:
    ks = tmp_path / "ks.json"
    runner.invoke(app, ["autoresearch", "halt", "--killswitch-path", str(ks), "--reason", "x"])
    result = runner.invoke(
        app, ["autoresearch", "status", "--killswitch-path", str(ks), "--ledger-path", str(tmp_path / "none.json")]
    )
    assert result.exit_code == 0
    assert "halted: True" in result.output
