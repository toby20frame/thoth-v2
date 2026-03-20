from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class TaskPriority(str, Enum):
    blocking = "blocking"
    important = "important"
    nice_to_have = "nice_to_have"


class PlannedTask(BaseModel):
    name: str = Field(description="Short task identifier")
    description: str = Field(description="What the task does")
    agent: str = Field(description="Which subagent: research, data, newsletter, system")
    force_cloud: bool = Field(default=False, description="Force cloud model")
    max_tokens: int = Field(default=2048, description="Token budget")


class CyclePlan(BaseModel):
    tasks: list[PlannedTask]
    research_prompts: list[str] = Field(default_factory=list)
    notes: str = Field(default="")


class AssessmentResult(BaseModel):
    overall_status: str = Field(description="green, yellow, or red")
    daily_cost_usd: float
    budget_remaining_today: float
    alerts: list[str] = Field(default_factory=list)
    strategy_health: dict = Field(default_factory=dict)


class DailyReport(BaseModel):
    status_line: str
    metrics: dict
    completed_tasks: list[str]
    failed_tasks: list[str]
    needs_human: list[str]
    interesting: list[str]
    research_prompts: list[str]

