"""Bounded team drill primitives for TaskChad planning.

The drill is deliberately state-first: convoy, team, mailbox, and team-loop
services remain the source of truth. Runtime turns are optional and run through
the existing no-tools team loop path.
"""

from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass

from orchestration.contract import DEFAULT_WORKSPACE_ID
from orchestration.convoy_service import ConvoyService
from orchestration.db import OrchestrationDB
from orchestration.mailbox_service import MailboxService
from orchestration.models import (
    AddTeamMemberInput,
    AgentMessage,
    ConvoyWithSubtasks,
    CreateConvoyInput,
    CreateSubtaskInput,
    CreateTeamSessionInput,
    SendMessageInput,
    Subtask,
    TeamSessionWithMembers,
)
from orchestration.observability import orchestration_span, update_observation
from orchestration.team_loop import (
    TeamLoopService,
    TeamLoopStepResult,
    result_to_dict,
)
from orchestration.team_service import TeamService

TASKCHAD_TARGET_URL = "https://www.taskchad.com/"
TASKCHAD_LEAD_AGENT_ID = "taskchad-drill-lead"
TASKCHAD_LEAD_AGENT_NAME = "TaskChad Drill Lead"


@dataclass(frozen=True)
class DrillRoleSpec:
    key: str
    agent_id: str
    agent_name: str
    subtask_title: str
    prompt: str
    depends_on_indexes: tuple[int, ...] = ()


@dataclass
class TaskChadDrillTurn:
    role: DrillRoleSpec
    step: TeamLoopStepResult


@dataclass
class TaskChadDrillResult:
    target_url: str
    convoy: ConvoyWithSubtasks
    team: TeamSessionWithMembers
    initial_messages: list[AgentMessage]
    role_turns: list[TaskChadDrillTurn]
    reviewer_turn: TaskChadDrillTurn
    revision_messages: list[AgentMessage]
    revision_turns: list[TaskChadDrillTurn]
    final_turn: TaskChadDrillTurn
    final_plan: str


TASKCHAD_ROLE_SPECS: tuple[DrillRoleSpec, ...] = (
    DrillRoleSpec(
        key="sales",
        agent_id="taskchad-sales",
        agent_name="TaskChad Sales",
        subtask_title="Sales follow-up plan",
        prompt=(
            "Review the TaskChad page as Sales. Produce a concise follow-up plan: "
            "target buyer, first conversation hook, qualification questions, CTA, "
            "and one objection to pre-handle."
        ),
    ),
    DrillRoleSpec(
        key="marketing",
        agent_id="taskchad-marketing",
        agent_name="TaskChad Marketing",
        subtask_title="Marketing positioning plan",
        prompt=(
            "Review the TaskChad page as Marketing. Produce concise positioning: "
            "primary promise, proof gaps, message hierarchy, credibility signals, "
            "and one offer clarity improvement."
        ),
    ),
    DrillRoleSpec(
        key="frontend_product",
        agent_id="taskchad-product",
        agent_name="TaskChad Frontend/Product",
        subtask_title="Frontend and product page review",
        prompt=(
            "Review the TaskChad page as Frontend/Product. Produce concise page "
            "improvements: above-the-fold clarity, conversion path, friction points, "
            "mobile/readability checks, and one implementation task."
        ),
    ),
    DrillRoleSpec(
        key="ops",
        agent_id="taskchad-ops",
        agent_name="TaskChad Ops",
        subtask_title="Ops execution plan",
        prompt=(
            "Review the TaskChad page as Ops. Produce a concise execution plan: "
            "owners, task order, instrumentation, follow-up workflow, and one risk "
            "that could stall delivery."
        ),
    ),
    DrillRoleSpec(
        key="adversarial_reviewer",
        agent_id="taskchad-reviewer",
        agent_name="TaskChad Adversarial Reviewer",
        subtask_title="Adversarial critique",
        prompt=(
            "Challenge the Sales, Marketing, Product, and Ops turns. Identify the "
            "highest-risk weak claim, missing proof, unclear buyer, and first "
            "implementation trap. Keep it direct and evidence-seeking."
        ),
        depends_on_indexes=(0, 1, 2, 3),
    ),
    DrillRoleSpec(
        key="final_plan",
        agent_id="taskchad-synthesizer",
        agent_name="TaskChad Plan Synthesizer",
        subtask_title="Final actionable plan",
        prompt=(
            "Synthesize the role turns and adversarial critique into one concise "
            "TaskChad plan covering positioning, page improvements, sales follow-up, "
            "ops tasks, and validation signals."
        ),
        depends_on_indexes=(4,),
    ),
)


class TaskChadTeamDrillService:
    """Runs one bounded TaskChad multi-role planning drill."""

    def __init__(self, db: OrchestrationDB):
        self.db = db
        self.convoy_svc = ConvoyService(db)
        self.mailbox_svc = MailboxService(db)
        self.team_svc = TeamService(db)
        self.loop_svc = TeamLoopService(db)

    def run_taskchad_drill(
        self,
        *,
        target_url: str = TASKCHAD_TARGET_URL,
        use_runtime: bool = False,
        runtime_lane: str | None = None,
        workspace_id: int = DEFAULT_WORKSPACE_ID,
    ) -> TaskChadDrillResult:
        """Create a team drill, run bounded written turns, and return the plan."""
        target_url = (target_url or TASKCHAD_TARGET_URL).strip()
        if not target_url:
            raise ValueError("target_url is required")

        with orchestration_span(
            "team_drill.run_taskchad_drill",
            metadata={
                "target_url": target_url,
                "use_runtime": use_runtime,
                "runtime_lane": runtime_lane,
            },
            trace_metadata={"feature_phase": 11, "target_url": target_url},
            expected_exceptions=(ValueError,),
        ):
            convoy = self._create_convoy(target_url, workspace_id=workspace_id)
            team = self._create_team(convoy, target_url=target_url, workspace_id=workspace_id)
            initial_messages = self._seed_initial_briefs(
                target_url=target_url,
                convoy_id=convoy.convoy.id,
                workspace_id=workspace_id,
            )

            role_turns: list[TaskChadDrillTurn] = []
            for spec in TASKCHAD_ROLE_SPECS[:4]:
                subtask = self._subtask_for_agent(convoy.subtasks, spec.agent_id)
                step = self.loop_svc.run_member_step(
                    team.session.id,
                    spec.agent_id,
                    subtask_id=subtask.id,
                    reply_body=self._default_role_reply(spec, target_url),
                    use_runtime=use_runtime,
                    runtime_lane=runtime_lane,
                    complete=True,
                    workspace_id=workspace_id,
                )
                role_turns.append(TaskChadDrillTurn(role=spec, step=step))

            reviewer_spec = TASKCHAD_ROLE_SPECS[4]
            reviewer_subtask = self._subtask_for_agent(convoy.subtasks, reviewer_spec.agent_id)
            self._send_reviewer_brief(
                target_url=target_url,
                convoy_id=convoy.convoy.id,
                reviewer=reviewer_spec,
                role_turns=role_turns,
                workspace_id=workspace_id,
            )
            reviewer_step = self.loop_svc.run_member_step(
                team.session.id,
                reviewer_spec.agent_id,
                subtask_id=reviewer_subtask.id,
                reply_body=self._default_reviewer_reply(target_url, role_turns),
                use_runtime=use_runtime,
                runtime_lane=runtime_lane,
                complete=True,
                workspace_id=workspace_id,
            )
            reviewer_turn = TaskChadDrillTurn(role=reviewer_spec, step=reviewer_step)

            revision_messages = self._send_revision_briefs(
                target_url=target_url,
                convoy_id=convoy.convoy.id,
                role_turns=role_turns,
                reviewer_turn=reviewer_turn,
                workspace_id=workspace_id,
            )
            revision_turns: list[TaskChadDrillTurn] = []
            for spec, subtask in zip(TASKCHAD_ROLE_SPECS[:4], convoy.subtasks[5:9]):
                step = self.loop_svc.run_member_step(
                    team.session.id,
                    spec.agent_id,
                    subtask_id=subtask.id,
                    reply_body=self._default_revision_reply(spec, target_url),
                    use_runtime=use_runtime,
                    runtime_lane=runtime_lane,
                    complete=True,
                    workspace_id=workspace_id,
                )
                revision_turns.append(TaskChadDrillTurn(role=spec, step=step))

            final_spec = TASKCHAD_ROLE_SPECS[5]
            final_subtask = convoy.subtasks[9]
            self._send_synthesis_brief(
                target_url=target_url,
                convoy_id=convoy.convoy.id,
                synthesizer=final_spec,
                role_turns=role_turns,
                reviewer_turn=reviewer_turn,
                revision_turns=revision_turns,
                workspace_id=workspace_id,
            )
            final_step = self.loop_svc.run_member_step(
                team.session.id,
                final_spec.agent_id,
                subtask_id=final_subtask.id,
                reply_body=self._default_final_plan(target_url),
                use_runtime=use_runtime,
                runtime_lane=runtime_lane,
                complete=True,
                workspace_id=workspace_id,
            )
            final_turn = TaskChadDrillTurn(role=final_spec, step=final_step)

            refreshed_convoy = self.convoy_svc.get_convoy(
                convoy.convoy.id,
                workspace_id=workspace_id,
            )
            refreshed_team = self.team_svc.get_team_session(
                team.session.id,
                workspace_id=workspace_id,
            )
            if refreshed_convoy is None or refreshed_team is None:
                raise RuntimeError("TaskChad drill state disappeared after run")

            final_plan = final_step.reply.body if final_step.reply else ""
            update_observation(
                metadata={
                    "convoy_id": refreshed_convoy.convoy.id,
                    "team_id": refreshed_team.session.id,
                    "role_turn_count": len(role_turns),
                    "convoy_status": refreshed_convoy.convoy.status,
                },
                output={"final_plan_chars": len(final_plan)},
            )
            return TaskChadDrillResult(
                target_url=target_url,
                convoy=refreshed_convoy,
                team=refreshed_team,
                initial_messages=initial_messages,
                role_turns=role_turns,
                reviewer_turn=reviewer_turn,
                revision_messages=revision_messages,
                revision_turns=revision_turns,
                final_turn=final_turn,
                final_plan=final_plan,
            )

    def _create_convoy(
        self,
        target_url: str,
        *,
        workspace_id: int,
    ) -> ConvoyWithSubtasks:
        initial_subtasks = [
            CreateSubtaskInput(
                title=spec.subtask_title,
                description=f"{spec.prompt}\n\nTarget page: {target_url}",
                assigned_agent_id=spec.agent_id,
                assigned_agent_name=spec.agent_name,
                depends_on_subtask_indexes=list(spec.depends_on_indexes),
                metadata=json.dumps(
                    {
                        "drill": "taskchad_team_drill",
                        "role": spec.key,
                        "round": "initial",
                        "target_url": target_url,
                    },
                    sort_keys=True,
                ),
            )
            for spec in TASKCHAD_ROLE_SPECS[:4]
        ]
        reviewer = TASKCHAD_ROLE_SPECS[4]
        reviewer_subtask = CreateSubtaskInput(
            title=reviewer.subtask_title,
            description=f"{reviewer.prompt}\n\nTarget page: {target_url}",
            assigned_agent_id=reviewer.agent_id,
            assigned_agent_name=reviewer.agent_name,
            depends_on_subtask_indexes=[0, 1, 2, 3],
            metadata=json.dumps(
                {
                    "drill": "taskchad_team_drill",
                    "role": reviewer.key,
                    "round": "critique",
                    "target_url": target_url,
                },
                sort_keys=True,
            ),
        )
        revision_subtasks = [
            CreateSubtaskInput(
                title=f"{spec.agent_name} revised plan",
                description=(
                    f"Revise the {spec.key} plan after adversarial review and peer context.\n\n"
                    f"Target page: {target_url}"
                ),
                assigned_agent_id=spec.agent_id,
                assigned_agent_name=spec.agent_name,
                depends_on_subtask_indexes=[4],
                metadata=json.dumps(
                    {
                        "drill": "taskchad_team_drill",
                        "role": spec.key,
                        "round": "revision",
                        "target_url": target_url,
                    },
                    sort_keys=True,
                ),
            )
            for spec in TASKCHAD_ROLE_SPECS[:4]
        ]
        synthesizer = TASKCHAD_ROLE_SPECS[5]
        final_subtask = CreateSubtaskInput(
            title=synthesizer.subtask_title,
            description=f"{synthesizer.prompt}\n\nTarget page: {target_url}",
            assigned_agent_id=synthesizer.agent_id,
            assigned_agent_name=synthesizer.agent_name,
            depends_on_subtask_indexes=[5, 6, 7, 8],
            metadata=json.dumps(
                {
                    "drill": "taskchad_team_drill",
                    "role": synthesizer.key,
                    "round": "synthesis",
                    "target_url": target_url,
                },
                sort_keys=True,
            ),
        )
        subtasks = [
            *initial_subtasks,
            reviewer_subtask,
            *revision_subtasks,
            final_subtask,
        ]
        return self.convoy_svc.create_convoy(
            CreateConvoyInput(
                title="TaskChad real team drill",
                description=(
                    "Bounded multi-role drill for TaskChad positioning, page clarity, "
                    "sales follow-up, execution planning, adversarial critique, "
                    "role revisions, and final synthesis."
                ),
                created_by=TASKCHAD_LEAD_AGENT_ID,
                repo_path=None,
                decomposition_mode="manual",
                subtasks=subtasks,
            ),
            workspace_id=workspace_id,
        )

    def _create_team(
        self,
        convoy: ConvoyWithSubtasks,
        *,
        target_url: str,
        workspace_id: int,
    ) -> TeamSessionWithMembers:
        team = self.team_svc.create_team_session(
            CreateTeamSessionInput(
                team_name="TaskChad Team Drill",
                lead_agent_id=TASKCHAD_LEAD_AGENT_ID,
                lead_agent_name=TASKCHAD_LEAD_AGENT_NAME,
                convoy_id=convoy.convoy.id,
                backend_type="local",
                metadata=json.dumps(
                    {
                        "drill": "taskchad_team_drill",
                        "target_url": target_url,
                    },
                    sort_keys=True,
                ),
            ),
            workspace_id=workspace_id,
        )
        for spec in TASKCHAD_ROLE_SPECS:
            subtask = self._subtask_for_agent(convoy.subtasks, spec.agent_id)
            self.team_svc.add_member(
                team.session.id,
                AddTeamMemberInput(
                    agent_id=spec.agent_id,
                    agent_name=spec.agent_name,
                    role="worker",
                    subtask_id=subtask.id,
                ),
                workspace_id=workspace_id,
            )
        refreshed = self.team_svc.get_team_session(team.session.id, workspace_id=workspace_id)
        if refreshed is None:
            raise RuntimeError(f"Failed to read back team session {team.session.id}")
        return refreshed

    def _seed_initial_briefs(
        self,
        *,
        target_url: str,
        convoy_id: int,
        workspace_id: int,
    ) -> list[AgentMessage]:
        messages: list[AgentMessage] = []
        for spec in TASKCHAD_ROLE_SPECS[:4]:
            messages.append(
                self.mailbox_svc.send_message(
                    SendMessageInput(
                        from_agent=TASKCHAD_LEAD_AGENT_ID,
                        recipients=[spec.agent_id],
                        convoy_id=convoy_id,
                        subject=f"TaskChad drill brief: {spec.agent_name}",
                        body=(
                            f"Target page: {target_url}\n\n"
                            f"{spec.prompt}\n\n"
                            "Return one bounded written turn. Do not use tools. "
                            "Name concrete improvements and handoff needs."
                        ),
                        message_type="message",
                        msg_type="task_assignment",
                    ),
                    workspace_id=workspace_id,
                )
            )
        return messages

    def _send_reviewer_brief(
        self,
        *,
        target_url: str,
        convoy_id: int,
        reviewer: DrillRoleSpec,
        role_turns: list[TaskChadDrillTurn],
        workspace_id: int,
    ) -> AgentMessage:
        body = (
            f"Target page: {target_url}\n\n"
            f"{reviewer.prompt}\n\n"
            "Role outputs:\n"
            f"{self._format_turns(role_turns)}"
        )
        return self.mailbox_svc.send_message(
            SendMessageInput(
                from_agent=TASKCHAD_LEAD_AGENT_ID,
                recipients=[reviewer.agent_id],
                convoy_id=convoy_id,
                subject="TaskChad adversarial review brief",
                body=body,
                message_type="message",
                msg_type="verifier_feedback",
            ),
            workspace_id=workspace_id,
        )

    def _send_synthesis_brief(
        self,
        *,
        target_url: str,
        convoy_id: int,
        synthesizer: DrillRoleSpec,
        role_turns: list[TaskChadDrillTurn],
        reviewer_turn: TaskChadDrillTurn,
        revision_turns: list[TaskChadDrillTurn],
        workspace_id: int,
    ) -> AgentMessage:
        reviewer_body = reviewer_turn.step.reply.body if reviewer_turn.step.reply else ""
        body = (
            f"Target page: {target_url}\n\n"
            f"{synthesizer.prompt}\n\n"
            "Initial role outputs:\n"
            f"{self._format_turns(role_turns)}\n\n"
            f"Adversarial critique:\n{reviewer_body}\n\n"
            "Revised role outputs:\n"
            f"{self._format_turns(revision_turns)}"
        )
        return self.mailbox_svc.send_message(
            SendMessageInput(
                from_agent=TASKCHAD_LEAD_AGENT_ID,
                recipients=[synthesizer.agent_id],
                convoy_id=convoy_id,
                subject="TaskChad final synthesis brief",
                body=body,
                message_type="message",
                msg_type="work_handoff",
            ),
            workspace_id=workspace_id,
        )

    def _send_revision_briefs(
        self,
        *,
        target_url: str,
        convoy_id: int,
        role_turns: list[TaskChadDrillTurn],
        reviewer_turn: TaskChadDrillTurn,
        workspace_id: int,
    ) -> list[AgentMessage]:
        reviewer_body = reviewer_turn.step.reply.body if reviewer_turn.step.reply else ""
        peer_context = self._format_turns(role_turns)
        messages: list[AgentMessage] = []
        for turn in role_turns:
            messages.append(
                self.mailbox_svc.send_message(
                    SendMessageInput(
                        from_agent=TASKCHAD_ROLE_SPECS[4].agent_id,
                        recipients=[turn.role.agent_id],
                        convoy_id=convoy_id,
                        subject=f"Revision interrupt: {turn.role.agent_name}",
                        body=(
                            f"Target page: {target_url}\n\n"
                            "Your first pass was useful, but the reviewer and peer context "
                            "raised gaps. Revise your plan by accepting, rejecting, or "
                            "narrowing the critique from your discipline's point of view.\n\n"
                            f"Reviewer critique:\n{reviewer_body}\n\n"
                            f"Peer context:\n{peer_context}"
                        ),
                        message_type="interrupt",
                        msg_type="verifier_feedback",
                    ),
                    workspace_id=workspace_id,
                )
            )
        return messages

    @staticmethod
    def _subtask_for_agent(subtasks: list[Subtask], agent_id: str) -> Subtask:
        for subtask in subtasks:
            if subtask.assigned_agent_id == agent_id:
                return subtask
        raise ValueError(f"No subtask assigned to {agent_id}")

    @staticmethod
    def _format_turns(turns: list[TaskChadDrillTurn]) -> str:
        lines: list[str] = []
        for turn in turns:
            body = turn.step.reply.body if turn.step.reply else ""
            lines.append(f"- {turn.role.agent_name}: {body}")
        return "\n".join(lines)

    @staticmethod
    def _default_role_reply(spec: DrillRoleSpec, target_url: str) -> str:
        replies = {
            "sales": (
                f"Sales plan for {target_url}: position TaskChad around reclaiming operator time, "
                "not generic automation. Lead with a concrete pain audit, qualify by "
                "current follow-up volume and missed task cost, then ask for one workflow "
                "to automate this week. Pre-handle the objection that this is another "
                "chatbot by showing the task-to-owner follow-up loop."
            ),
            "marketing": (
                f"Marketing plan for {target_url}: make the page answer who it serves, "
                "what outcome it creates, and what proof exists in the first viewport. "
                "Add sharper offer language, visible workflow examples, a proof strip, "
                "and one CTA tied to a TaskChad audit. The weak point to "
                "fix first is credibility without concrete before/after evidence."
            ),
            "frontend_product": (
                f"Product/page plan for {target_url}: tighten the hero around the "
                "literal TaskChad offer, show the task intake-to-follow-up flow, add a "
                "compact proof/demo section, and keep the CTA visible after scroll. "
                "Implementation task: add a page section that maps buyer pain, "
                "TaskChad action, and measurable result in one scan-friendly row."
            ),
            "ops": (
                f"Ops plan for {target_url}: ship in four steps: clarify the offer copy, "
                "add proof/demo assets, wire lead capture to sales follow-up, and instrument "
                "CTA/source tracking. Owners should be copy, frontend, sales ops, and "
                "analytics. Main stall risk is debating broad brand "
                "positioning instead of proving one offer with one page and one follow-up loop."
            ),
        }
        return replies.get(spec.key, spec.prompt)

    @staticmethod
    def _default_reviewer_reply(target_url: str, role_turns: list[TaskChadDrillTurn]) -> str:
        role_names = ", ".join(turn.role.key for turn in role_turns)
        return (
            f"Adversarial review for {target_url}: the combined {role_names} plan is "
            "useful, but it can still fail by staying generic. The page must prove a "
            "specific buyer, a specific repeated task problem, and a specific follow-up "
            "outcome. Missing proof is the biggest risk. First implementation trap: "
            "adding sections without a tracked CTA and sales follow-up owner."
        )

    @staticmethod
    def _default_revision_reply(spec: DrillRoleSpec, target_url: str) -> str:
        replies = {
            "sales": (
                f"Sales revision for {target_url}: narrow the buyer to busy service "
                "operators and agency owners who already lose money on missed follow-ups. "
                "I disagree with making the CTA a vague demo; make it a task-leak audit. "
                "Sales owns lead routing, first-call questions, objection log, and the "
                "promise that one workflow gets mapped before any broad automation pitch."
            ),
            "marketing": (
                f"Marketing revision for {target_url}: accept the proof critique and lead "
                "with one concrete before/after workflow, not brand language. The hierarchy "
                "should be buyer pain, repeated task leak, TaskChad action, visible result, "
                "then audit CTA. Marketing owns proof copy, workflow example, testimonial "
                "slot, and a tighter headline that avoids generic AI language."
            ),
            "frontend_product": (
                f"Product revision for {target_url}: push back on adding too many sections. "
                "Ship one focused conversion path: hero, workflow row, proof/demo strip, "
                "audit CTA, and follow-up expectation. Frontend owns the page section, "
                "CTA persistence, mobile scanability, and analytics hooks so the release "
                "can prove whether the revised story converts."
            ),
            "ops": (
                f"Ops revision for {target_url}: agree that ownership is the failure point. "
                "The release should have named owners for copy, page build, lead routing, "
                "and analytics before writing more content. Ops owns the checklist, launch "
                "order, QA, and daily readout of CTA clicks, booked audits, completed "
                "follow-ups, and objections."
            ),
        }
        return replies.get(spec.key, spec.prompt)

    @staticmethod
    def _default_final_plan(target_url: str) -> str:
        return (
            f"Final revised TaskChad plan for {target_url}:\n"
            "1. Buyer: focus on busy service operators and agency owners losing money "
            "to missed tasks and follow-ups.\n"
            "2. Offer: replace vague demo language with a task-leak audit that maps one "
            "workflow before pitching broader automation.\n"
            "3. Page: ship a hero, workflow row, proof/demo strip, persistent audit CTA, "
            "and clear follow-up expectation.\n"
            "4. Ownership: Sales owns lead routing and objections; Marketing owns proof "
            "and headline; Product owns page/CTA; Ops owns QA, launch order, and readout.\n"
            "5. Validation: track CTA rate, booked audits, completed follow-ups, and "
            "first-call objections before expanding the page."
        )


def taskchad_drill_turn_to_dict(turn: TaskChadDrillTurn) -> dict:
    return {
        "role": turn.role.key,
        "role_name": turn.role.agent_name,
        "agent_id": turn.role.agent_id,
        "subtask_id": turn.step.subtask_id,
        "action": turn.step.action,
        "status": turn.step.subtask_after.status if turn.step.subtask_after else None,
        "completed": turn.step.completed,
        "reply": dataclasses.asdict(turn.step.reply) if turn.step.reply else None,
        "step": result_to_dict(turn.step),
    }


def taskchad_drill_result_to_dict(result: TaskChadDrillResult) -> dict:
    return {
        "target_url": result.target_url,
        "team_id": result.team.session.id,
        "convoy_id": result.convoy.convoy.id,
        "team": {
            "session": dataclasses.asdict(result.team.session),
            "members": [dataclasses.asdict(member) for member in result.team.members],
        },
        "convoy": {
            "convoy": dataclasses.asdict(result.convoy.convoy),
            "subtasks": [dataclasses.asdict(subtask) for subtask in result.convoy.subtasks],
            "edges": [dataclasses.asdict(edge) for edge in result.convoy.edges],
        },
        "initial_message_count": len(result.initial_messages),
        "revision_message_count": len(result.revision_messages),
        "role_turns": [taskchad_drill_turn_to_dict(turn) for turn in result.role_turns],
        "reviewer_turn": taskchad_drill_turn_to_dict(result.reviewer_turn),
        "revision_turns": [
            taskchad_drill_turn_to_dict(turn)
            for turn in result.revision_turns
        ],
        "final_turn": taskchad_drill_turn_to_dict(result.final_turn),
        "final_plan": result.final_plan,
    }
