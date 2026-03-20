import json
import time
from router import ModelRouter, extract_text
from agent import SubAgent
from state import (
    start_cycle, finish_cycle, log_task, log_cost,
    get_daily_cost, get_pending_escalations
)
from memory import recall_relevant
from models import CyclePlan, PlannedTask, AssessmentResult, DailyReport
from config import MAX_DAILY_COST_USD
from tools.base import TOOL_REGISTRY, TOOL_DISPATCH

# Import tools so they self-register
import tools.system
import tools.usaspending


class Coordinator:
    def __init__(self):
        self.router = ModelRouter()
        self.cycle_id = None

    def run_cycle(self):
        self.cycle_id = start_cycle()
        try:
            state = self.wake()
            assessment = self.assess(state)
            plan = self.plan(assessment, state)
            results = self.execute(plan)
            self.report(assessment, plan, results)
            finish_cycle(self.cycle_id, "success")
            print(f"Cycle {self.cycle_id} complete.")
        except Exception as e:
            finish_cycle(self.cycle_id, f"failed: {e}")
            print(f"Cycle {self.cycle_id} failed: {e}")
            raise

    def wake(self) -> dict:
        """WAKE: gather current state. All local, zero API cost."""
        daily_cost = get_daily_cost()
        escalations = get_pending_escalations()
        return {
            "timestamp": time.time(),
            "daily_cost_usd": daily_cost,
            "budget_remaining": MAX_DAILY_COST_USD - daily_cost,
            "pending_escalations": len(escalations),
            "escalations": escalations,
        }

    def assess(self, state: dict) -> AssessmentResult:
        """ASSESS: compare metrics against thresholds. No API cost."""
        alerts = []
        if state["daily_cost_usd"] > MAX_DAILY_COST_USD * 0.8:
            alerts.append(f"Daily cost at ${state['daily_cost_usd']:.2f} — approaching limit")
        if state["budget_remaining"] <= 0:
            alerts.append("DAILY BUDGET EXHAUSTED — no cloud API calls today")

        overall = "green"
        if alerts:
            overall = "yellow"
        if state["budget_remaining"] <= 0:
            overall = "red"

        return AssessmentResult(
            overall_status=overall,
            daily_cost_usd=state["daily_cost_usd"],
            budget_remaining_today=state["budget_remaining"],
            alerts=alerts,
            strategy_health={},
        )

    def plan(self, assessment: AssessmentResult, state: dict) -> CyclePlan:
        """PLAN: determine tasks for this cycle. One LLM call."""
        if assessment.budget_remaining_today <= 0:
            return CyclePlan(
                tasks=[PlannedTask(
                    name="local_maintenance",
                    description="Run local-only maintenance tasks",
                    agent="system",
                    force_cloud=False,
                )],
                notes="Budget exhausted — local tasks only",
            )

        planning_prompt = f"""You are the Thoth coordinator. Based on current state, decide what tasks to run.

Current state:
- Daily cost: ${assessment.daily_cost_usd:.2f} of ${MAX_DAILY_COST_USD:.2f} budget
- Alerts: {assessment.alerts if assessment.alerts else 'None'}
- Pending escalations: {state['pending_escalations']}

Available agents:
- research: Queries APIs (USAspending.gov, FRED, SEC)
- data: Processes and enriches data
- newsletter: Generates newsletter drafts and analysis
- system: Checks system health, runs maintenance

Respond with ONLY valid JSON:
{{"tasks": [{{"name": "string", "description": "string", "agent": "string", "force_cloud": false, "max_tokens": 2048}}], "research_prompts": [], "notes": "string"}}"""

        result = self.router.call(
            messages=[{"role": "user", "content": planning_prompt}],
            system="You are a task planner. Respond with valid JSON only. No markdown, no explanation.",
            force_cloud=False,
        )

        log_cost(
            model=result["model_used"],
            task_type="planning",
            input_tokens=result["input_tokens"],
            output_tokens=result["output_tokens"],
            cost_usd=result["cost_usd"],
        )

        try:
            clean = result["text"].strip()
            if clean.startswith("```"):
                lines = clean.split("\n")
                clean = "\n".join(lines[1:-1])
            plan_data = json.loads(clean)
            return CyclePlan(**plan_data)
        except Exception as e:
            return CyclePlan(
                tasks=[PlannedTask(
                    name="system_check",
                    description="Run basic system health check",
                    agent="system",
                    force_cloud=False,
                )],
                notes=f"Planning failed ({e}), running safe default",
            )

    def execute(self, plan: CyclePlan) -> list:
        """EXECUTE: run each planned task."""
        results = []
        for task in plan.tasks:
            if task.force_cloud and get_daily_cost() >= MAX_DAILY_COST_USD:
                results.append({"task": task.name, "status": "skipped", "reason": "budget exhausted"})
                continue

            subagent = SubAgent(
                router=self.router,
                name=task.agent,
                system_prompt=self._get_agent_prompt(task.agent),
                tools=TOOL_REGISTRY.get(task.agent, []),
                tool_dispatch=TOOL_DISPATCH,
                force_cloud=task.force_cloud or self._needs_cloud(task.agent),
            )

            try:
                output = subagent.run(task.description)
                log_task(
                    cycle_id=self.cycle_id,
                    task_type=task.agent,
                    task_name=task.name,
                    status="success",
                    model_used=subagent.model_used,
                    input_tokens=subagent.total_input_tokens,
                    output_tokens=subagent.total_output_tokens,
                    cost_usd=subagent.total_cost,
                    result_summary=output[:500],
                )
                results.append({
                    "task": task.name, "status": "success",
                    "output": output[:500], "cost": subagent.total_cost,
                })
            except Exception as e:
                log_task(
                    cycle_id=self.cycle_id,
                    task_type=task.agent,
                    task_name=task.name,
                    status="failed",
                    error_message=str(e),
                )
                results.append({"task": task.name, "status": "failed", "error": str(e)})

        return results

    def report(self, assessment: AssessmentResult, plan: CyclePlan, results: list):
        """REPORT: generate summary. Prints for now, Discord integration later."""
        completed = [r for r in results if r["status"] == "success"]
        failed = [r for r in results if r["status"] == "failed"]
        total_cost = sum(r.get("cost", 0) for r in results)

        report = DailyReport(
            status_line=f"Cycle complete — {assessment.overall_status.upper()} — "
                        f"{len(completed)} done, {len(failed)} failed",
            metrics={
                "daily_cost": f"${assessment.daily_cost_usd + total_cost:.4f}",
                "tasks_completed": len(completed),
                "tasks_failed": len(failed),
            },
            completed_tasks=[f"{r['task']}: {r.get('output', '')[:100]}" for r in completed],
            failed_tasks=[f"{r['task']}: {r.get('error', 'unknown')}" for r in failed],
            needs_human=[],
            interesting=[],
            research_prompts=plan.research_prompts,
        )

        print("\n" + "=" * 60)
        print(f"  {report.status_line}")
        print("=" * 60)
        for k, v in report.metrics.items():
            print(f"  {k}: {v}")
        if report.completed_tasks:
            print("\n  Completed:")
            for t in report.completed_tasks:
                print(f"    ✓ {t[:80]}")
        if report.failed_tasks:
            print("\n  Failed:")
            for t in report.failed_tasks:
                print(f"    ✗ {t[:80]}")
        print("=" * 60 + "\n")

    def _needs_cloud(self, agent_name: str) -> bool:
        """Agents that use tools or need quality output must use cloud."""
        return agent_name in ("research", "newsletter")

    def _get_agent_prompt(self, agent_name: str) -> str:
        prompts = {
            "research": "You are a financial research agent. Use tools to gather data. Be concise.",
            "data": "You are a data processing agent. Clean and enrich data. Report anomalies.",
            "newsletter": "You are a financial newsletter writer. Every number must be sourced.",
            "system": "You are a system monitor. Check health and report issues briefly.",
        }
        return prompts.get(agent_name, "You are a helpful assistant.")

