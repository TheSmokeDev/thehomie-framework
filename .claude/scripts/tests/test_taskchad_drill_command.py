from __future__ import annotations

import asyncio
from pathlib import Path
import sys


CHAT_DIR = Path(__file__).resolve().parents[2] / "chat"
SCRIPTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CHAT_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))

import commands  # noqa: E402
import config  # noqa: E402
import core_handlers  # noqa: E402
from extension_manager import ExtensionManager  # noqa: E402
from runtime.base import RuntimeResult  # noqa: E402


def test_taskchad_drill_command_is_router_registered() -> None:
    command_rows = {name: (desc, typ, role) for name, desc, typ, role in commands.COMMANDS}

    desc, typ, role = command_rows["taskchaddrill"]
    assert typ == "router"
    assert role == "admin"
    assert "TaskChad" in desc
    assert core_handlers.CORE_HANDLERS["taskchaddrill"] is core_handlers.handle_taskchaddrill


def test_taskchad_drill_command_appears_in_cabinet_help() -> None:
    manager = ExtensionManager()
    manager.register_core_commands(commands.COMMANDS, commands.CATEGORIES, core_handlers.CORE_HANDLERS)

    help_text = manager.get_help_text(user_role="admin")

    assert "*Cabinet*" in help_text
    assert "/taskchaddrill" in help_text


def test_taskchad_drill_command_runs_default_bounded_drill(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(config, "ORCHESTRATION_DB_PATH", tmp_path / "taskchad_drill.db")

    reply = asyncio.run(
        core_handlers.handle_taskchaddrill(
            adapter=None,
            incoming=None,
            args="",
        )
    )

    assert "*TaskChad Team Drill*" in reply
    assert "Target: `https://www.taskchad.com/`" in reply
    assert "4 proposals, 1 adversarial critique, 4 revisions, 1 final synthesis" in reply
    assert "Progress: `10/10` subtasks" in reply
    assert "Runtime turns: `off`" in reply
    assert "Final revised TaskChad plan" in reply


def test_taskchad_drill_command_runs_runtime_drill_from_async_handler(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(config, "ORCHESTRATION_DB_PATH", tmp_path / "taskchad_runtime.db")
    calls = []

    async def fake_run_with_runtime_lanes(request):
        calls.append(request)
        return RuntimeResult(
            text=f"Runtime command turn {len(calls)}",
            runtime_lane=request.runtime_lane or "generic_runtime",
            provider="openai-codex",
            model="gpt-test",
            cost_usd=0.0,
            tool_call_count=0,
        )

    monkeypatch.setattr(
        "orchestration.team_loop.run_with_runtime_lanes",
        fake_run_with_runtime_lanes,
    )

    reply = asyncio.run(
        core_handlers.handle_taskchaddrill(
            adapter=None,
            incoming=None,
            args="--runtime --lane generic_runtime",
        )
    )

    assert len(calls) == 10
    assert "Runtime turns: `on`" in reply
    assert "Runtime lane: `generic_runtime`" in reply
    assert "Runtime metadata: `10` turns" in reply
    assert "providers `openai-codex`" in reply
    assert "models `gpt-test`" in reply
    assert "tools `0`" in reply
    assert "Runtime command turn 10" in reply


def test_taskchad_drill_rejects_relative_target_url() -> None:
    reply = asyncio.run(
        core_handlers.handle_taskchaddrill(
            adapter=None,
            incoming=None,
            args="--target-url taskchad.com",
        )
    )

    assert "absolute http(s)" in reply
