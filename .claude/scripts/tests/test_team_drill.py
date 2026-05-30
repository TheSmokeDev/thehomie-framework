"""TaskChad team drill tests."""

import sys
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from orchestration.db import OrchestrationDB  # noqa: E402
from orchestration.mailbox_service import MailboxService  # noqa: E402
from orchestration.team_drill import TaskChadTeamDrillService  # noqa: E402
from orchestration.team_service import TeamService  # noqa: E402


def test_taskchad_drill_runs_role_review_and_final_plan():
    db = OrchestrationDB(":memory:")
    try:
        result = TaskChadTeamDrillService(db).run_taskchad_drill()

        assert result.target_url == "https://www.taskchad.com/"
        assert result.convoy.convoy.status == "completed"
        assert result.team.session.team_name == "TaskChad Team Drill"
        assert len(result.team.members) == 7
        assert len(result.initial_messages) == 4
        assert len(result.role_turns) == 4
        assert len(result.revision_messages) == 4
        assert len(result.revision_turns) == 4
        assert all(turn.step.completed for turn in result.role_turns)
        assert result.reviewer_turn.step.subtask_before.status == "ready"
        assert result.reviewer_turn.step.completed is True
        assert all(turn.step.subtask_before.status == "ready" for turn in result.revision_turns)
        assert all(turn.step.completed for turn in result.revision_turns)
        assert result.final_turn.step.subtask_before.status == "ready"
        assert result.final_turn.step.completed is True
        assert result.final_turn.step.convoy_completed is True
        assert result.convoy.convoy.total_subtasks == 10
        assert result.convoy.convoy.completed_subtasks == 10
        assert "Final revised TaskChad plan" in result.final_plan
        assert "task-leak audit" in result.final_plan

        messages = MailboxService(db).get_convoy_messages(result.convoy.convoy.id)
        subjects = [entry.message.subject for entry in messages]
        bodies = [entry.message.body for entry in messages]
        assert "TaskChad adversarial review brief" in subjects
        assert "TaskChad final synthesis brief" in subjects
        assert len([s for s in subjects if s and s.startswith("Revision interrupt:")]) == 4
        assert any("Adversarial review" in body for body in bodies)
        assert any("Sales revision" in body for body in bodies)
        assert any("Final revised TaskChad plan" in body for body in bodies)
    finally:
        db.close()


def test_taskchad_drill_api_creates_completed_team_drill(tmp_path):
    db_path = tmp_path / "test_team_drill_api.db"
    with patch("config.ORCHESTRATION_DB_PATH", db_path):
        import importlib

        import orchestration.api as api_mod

        importlib.reload(api_mod)
        db, cs, ms, reg, team_svc = api_mod._get_services()
        api_mod._db = db
        api_mod._convoy_svc = cs
        api_mod._mailbox_svc = ms
        api_mod._executor_registry = reg
        api_mod._team_svc = team_svc
        try:
            client = TestClient(api_mod.app)
            response = client.post("/api/team/taskchad-drill", json={})

            assert response.status_code == 200
            body = response.json()
            assert body["target_url"] == "https://www.taskchad.com/"
            assert body["initial_message_count"] == 4
            assert body["revision_message_count"] == 4
            assert len(body["role_turns"]) == 4
            assert len(body["revision_turns"]) == 4
            assert body["reviewer_turn"]["completed"] is True
            assert body["final_turn"]["completed"] is True
            assert "Final revised TaskChad plan" in body["final_plan"]
            assert body["convoy"]["convoy"]["status"] == "completed"
            assert body["convoy"]["convoy"]["total_subtasks"] == 10

            team = TeamService(db).get_team_session(body["team_id"])
            assert team is not None
            assert len(team.members) == 7
        finally:
            db.close()
