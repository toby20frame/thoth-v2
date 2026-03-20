# Thoth V2 Builder Spec — Core Orchestration Layer

## What This Document Is

This is a specification for building the core orchestration layer of Thoth, an autonomous AI agent system running on a Jetson Orin Nano 8GB. Create all files described below in the current directory, following the architecture and patterns exactly.

## System Context

- **Hardware:** Jetson Orin Nano 8GB, ARM64, CUDA 12.6, 1TB NVMe at /mnt/nvme
- **OS:** Ubuntu 22.04, JetPack 6.2, Python 3.10.12
- **Workspace:** /mnt/nvme/thoth/ (symlinked to ~/thoth). Code goes in ~/thoth/core/
- **Existing databases:** ~/thoth/data/thoth_state.db, thoth_memory.db, thoth_calibration.db (already created with schemas — do NOT recreate them)
- **Ollama:** Running as systemd service on port 11434, model: qwen3:4b
- **Ollama returns thinking blocks:** qwen3:4b produces ThinkingBlock content alongside TextBlock. ALL response parsing MUST filter for text blocks only: `[b.text for b in resp.content if b.type == "text"]`
- **Ollama thinking suppression:** Append " /no_think" to prompts for local model calls to reduce token waste from reasoning
- **Cloud API key:** Set as environment variable ANTHROPIC_API_KEY (starts with sk-ant-). Do NOT load from file — use `anthropic.Anthropic()` with no arguments for cloud client.
- **Working cloud models:** `claude-haiku-4-5` (confirmed working, cheap), `claude-3-haiku-20240307` (fallback)
- **Claude Code CLI:** Installed at v2.1.63, authenticated. Available for heavy research via `claude -p` headless mode.
- **Discord bot:** Running at ~/.openclaw/workspace/scripts/discord_listener.py
- **Python packages installed:** anthropic 0.86.0, httpx 0.28.1, pydantic 2.12.5, discord.py 2.7.1, beautifulsoup4, pandas, psutil, playwright

## Architecture Decisions (Non-Negotiable)

1. **Raw Anthropic Python SDK for ALL LLM calls** — both local Ollama and cloud Claude. No LangChain, no CrewAI, no PydanticAI framework, no SmolAgents, no OpenAI SDK.

2. **Ollama via Anthropic SDK.** Use `anthropic.Anthropic(base_url="http://localhost:11434", api_key="ollama")` for local. Use `anthropic.Anthropic()` for cloud (picks up env var automatically).

3. **CRITICAL: Handle thinking blocks in ALL response parsing.** Ollama's qwen3:4b returns ThinkingBlock objects mixed with TextBlock objects. Never access `response.content[0].text` directly. Always use:
   ```python
   text_blocks = [b.text for b in response.content if b.type == "text" and hasattr(b, "text")]
   full_text = "\n".join(text_blocks)
   ```

4. **Append " /no_think" to local model prompts** to suppress thinking and save tokens. Do NOT append this to cloud Claude prompts.

5. **Pydantic BaseModel for data validation only.** Not the PydanticAI framework.

6. **SQLite for ALL state.** Databases already exist at ~/thoth/data/. Use WAL mode (already configured). Never recreate the databases.

7. **"LLM proposes, deterministic code executes."** The LLM returns structured JSON. Python code executes deterministically. The LLM never directly executes actions.

8. **Every API call is logged with token counts and cost.**

## File Structure to Create

```
~/thoth/core/
├── __init__.py          # Empty file
├── main.py              # Entry point — runs one decision cycle
├── coordinator.py       # Runs WAKE→ASSESS→PLAN→EXECUTE→REPORT→SLEEP
├── agent.py             # SubAgent class: agent loop with tool execution
├── router.py            # ModelRouter: routes between local Ollama and cloud Claude
├── tools/
│   ├── __init__.py      # Empty file
│   ├── base.py          # Tool registry and dispatch
│   ├── usaspending.py   # USAspending.gov API tools
│   └── system.py        # System health monitoring tools
├── state.py             # Interface to thoth_state.db
├── memory.py            # Interface to thoth_memory.db
├── calibration.py       # Interface to thoth_calibration.db
├── discord_report.py    # Format and print reports (Discord integration later)
├── config.py            # All configuration, thresholds, model names
└── models.py            # Pydantic models for structured data validation
```

## config.py

All configuration in one place. No magic numbers elsewhere.

```python
from pathlib import Path
import os

# Paths
THOTH_ROOT = Path("/mnt/nvme/thoth")
DATA_DIR = THOTH_ROOT / "data"
LOGS_DIR = THOTH_ROOT / "logs"

# Database paths (databases already exist — do NOT recreate)
STATE_DB = DATA_DIR / "thoth_state.db"
MEMORY_DB = DATA_DIR / "thoth_memory.db"
CALIBRATION_DB = DATA_DIR / "thoth_calibration.db"

# Local model config
LOCAL_MODEL = "qwen3:4b"
LOCAL_BASE_URL = "http://localhost:11434"
LOCAL_MAX_TOKENS = 500  # Higher than default to allow room after thinking tokens

# Cloud model config — ANTHROPIC_API_KEY is set in environment
CLOUD_MODEL = "claude-haiku-4-5"
CLOUD_FALLBACK_MODEL = "claude-3-haiku-20240307"

# Cost tracking (USD per million tokens)
MODEL_COSTS = {
    "qwen3:4b": {"input": 0.0, "output": 0.0},
    "claude-haiku-4-5": {"input": 1.0, "output": 5.0},
    "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
}

# Hardcoded constraints
MAX_DAILY_COST_USD = 2.00
MAX_RETRIES_PER_TASK = 3
MAX_AGENT_ITERATIONS = 10
RESERVE_BUDGET_USD = 40.00

# Thresholds for ASSESS phase
STRATEGY_COST_THRESHOLD_DAYS = 7
STRATEGY_FAIL_THRESHOLD_DAYS = 14
ERROR_RATE_THRESHOLD = 0.3

# Discord channel IDs (for future integration)
DISCORD_CHANNELS = {
    "commands": 1483512587172839565,
    "alerts": 1476379631224623365,
    "logs": 1476379705228787903,
    "general": 1476375559117213790,
}
```

## router.py

Routes between local Ollama and cloud Claude using the SAME Anthropic SDK.

```python
import anthropic
import time
from config import (
    LOCAL_MODEL, LOCAL_BASE_URL, LOCAL_MAX_TOKENS,
    CLOUD_MODEL, CLOUD_FALLBACK_MODEL, MODEL_COSTS,
    MAX_RETRIES_PER_TASK
)


def extract_text(response) -> str:
    """Extract text from response, filtering out thinking blocks.
    CRITICAL: Ollama qwen3:4b returns ThinkingBlock objects.
    Never access response.content[0].text directly.
    """
    text_parts = []
    for block in response.content:
        if block.type == "text" and hasattr(block, "text"):
            text_parts.append(block.text)
    return "\n".join(text_parts).strip()


class ModelRouter:
    def __init__(self):
        self.local = anthropic.Anthropic(
            base_url=LOCAL_BASE_URL,
            api_key="ollama"
        )
        # Cloud client picks up ANTHROPIC_API_KEY from environment
        self.cloud = anthropic.Anthropic()

    def classify_complexity(self, task: str, force_cloud: bool = False) -> str:
        if force_cloud:
            return "complex"
        simple_signals = [
            "summarize", "format", "extract", "classify", "list",
            "count", "parse", "convert", "filter", "check"
        ]
        task_lower = task.lower()
        if len(task) < 500 and any(s in task_lower for s in simple_signals):
            return "simple"
        complex_signals = [
            "analyze", "compare", "recommend", "evaluate", "write",
            "generate newsletter", "research", "plan", "strategy"
        ]
        if any(s in task_lower for s in complex_signals):
            return "complex"
        if len(task) > 1500:
            return "complex"
        return "simple"

    def call(self, messages: list, system: str = "", tools: list = None,
             force_cloud: bool = False, max_tokens: int = None) -> dict:
        """
        Make an LLM call routed to the appropriate model.
        Returns dict: response, model_used, input_tokens, output_tokens, cost_usd, text
        """
        complexity = self.classify_complexity(
            messages[-1]["content"] if messages else "",
            force_cloud=force_cloud
        )

        is_local = (complexity == "simple")

        if is_local:
            client = self.local
            model = LOCAL_MODEL
            effective_max_tokens = max_tokens or LOCAL_MAX_TOKENS
            # Append /no_think to suppress thinking on local model
            messages = _append_no_think(messages)
        else:
            client = self.cloud
            model = CLOUD_MODEL
            effective_max_tokens = max_tokens or 2048

        kwargs = {
            "model": model,
            "max_tokens": effective_max_tokens,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system
        if tools and not is_local:
            # Only pass tools to cloud model — local models struggle with tool schemas
            kwargs["tools"] = tools

        # Retry with backoff
        response = None
        for attempt in range(MAX_RETRIES_PER_TASK):
            try:
                response = client.messages.create(**kwargs)
                break
            except anthropic.RateLimitError:
                time.sleep(2 ** attempt)
            except anthropic.APIConnectionError:
                if is_local:
                    # Local Ollama down — fall back to cloud
                    client = self.cloud
                    model = CLOUD_MODEL
                    kwargs["model"] = model
                    kwargs["max_tokens"] = max_tokens or 2048
                    # Remove /no_think for cloud
                    kwargs["messages"] = messages  # Original without /no_think
                    try:
                        response = client.messages.create(**kwargs)
                        break
                    except Exception:
                        raise
                if attempt == MAX_RETRIES_PER_TASK - 1:
                    raise
                time.sleep(1)
            except anthropic.APIStatusError as e:
                if e.status_code >= 500:
                    time.sleep(2 ** attempt)
                elif e.status_code == 404 and model == CLOUD_MODEL:
                    # Model not found, try fallback
                    model = CLOUD_FALLBACK_MODEL
                    kwargs["model"] = model
                    response = client.messages.create(**kwargs)
                    break
                else:
                    raise

        if response is None:
            return {
                "response": None,
                "model_used": model,
                "input_tokens": 0,
                "output_tokens": 0,
                "cost_usd": 0,
                "text": "ERROR: API unreachable after retries",
            }

        # Calculate cost
        costs = MODEL_COSTS.get(model, {"input": 0, "output": 0})
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        cost = (input_tokens * costs["input"] + output_tokens * costs["output"]) / 1_000_000

        return {
            "response": response,
            "model_used": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost,
            "text": extract_text(response),
        }


def _append_no_think(messages: list) -> list:
    """Append /no_think to the last user message for local model calls."""
    if not messages:
        return messages
    modified = [m.copy() for m in messages]
    last = modified[-1]
    if last.get("role") == "user" and isinstance(last.get("content"), str):
        if "/no_think" not in last["content"]:
            last["content"] = last["content"] + " /no_think"
    return modified
```

## agent.py

Generic SubAgent class with agent loop and tool execution.

```python
import json
import time
from router import ModelRouter, extract_text
from config import MAX_AGENT_ITERATIONS, MAX_RETRIES_PER_TASK


class SubAgent:
    def __init__(self, router: ModelRouter, name: str, system_prompt: str,
                 tools: list = None, tool_dispatch: dict = None,
                 force_cloud: bool = False):
        self.router = router
        self.name = name
        self.system_prompt = system_prompt
        self.tools = tools or []
        self.tool_dispatch = tool_dispatch or {}
        self.force_cloud = force_cloud
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0
        self.model_used = ""

    def run(self, task: str) -> str:
        """Run the agent loop. Returns the final text response."""
        messages = [{"role": "user", "content": task}]

        for iteration in range(MAX_AGENT_ITERATIONS):
            result = self.router.call(
                messages=messages,
                system=self.system_prompt,
                tools=self.tools if self.tools else None,
                force_cloud=self.force_cloud,
            )

            response = result["response"]
            if response is None:
                return result["text"]  # Error message

            self.model_used = result["model_used"]
            self.total_input_tokens += result["input_tokens"]
            self.total_output_tokens += result["output_tokens"]
            self.total_cost += result["cost_usd"]

            messages.append({"role": "assistant", "content": response.content})

            # If no tool use, we're done
            if response.stop_reason != "tool_use":
                return extract_text(response)

            # Execute tool calls
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue

                execute_fn = self.tool_dispatch.get(block.name)
                if execute_fn is None:
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps({"error": f"Unknown tool: {block.name}"}),
                        "is_error": True,
                    })
                    continue

                # Retry loop for tool execution
                for attempt in range(MAX_RETRIES_PER_TASK):
                    try:
                        result_data = execute_fn(**block.input)
                        content = json.dumps(result_data) if isinstance(result_data, dict) else str(result_data)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": content,
                        })
                        break
                    except Exception as e:
                        if attempt == MAX_RETRIES_PER_TASK - 1:
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": f"Tool failed after {MAX_RETRIES_PER_TASK} attempts: {e}",
                                "is_error": True,
                            })

            messages.append({"role": "user", "content": tool_results})

        return f"Agent '{self.name}' hit max iterations ({MAX_AGENT_ITERATIONS})"
```

## tools/base.py

Tool registry. Tools self-register on import.

```python
# Global registries
TOOL_REGISTRY = {}   # agent_name -> list of tool JSON schemas
TOOL_DISPATCH = {}   # tool_name -> callable


def register_tool(agent_name: str, schema: dict, execute_fn: callable):
    if agent_name not in TOOL_REGISTRY:
        TOOL_REGISTRY[agent_name] = []
    TOOL_REGISTRY[agent_name].append(schema)
    TOOL_DISPATCH[schema["name"]] = execute_fn
```

## tools/system.py

System health monitoring tools.

```python
import shutil
import psutil
import httpx
from tools.base import register_tool


def check_system_health() -> dict:
    nvme = shutil.disk_usage("/mnt/nvme")
    root = shutil.disk_usage("/")
    mem = psutil.virtual_memory()

    try:
        resp = httpx.get("http://localhost:11434/api/tags", timeout=5)
        ollama_ok = resp.status_code == 200
    except Exception:
        ollama_ok = False

    return {
        "nvme_free_gb": round(nvme.free / (1024**3), 1),
        "root_free_gb": round(root.free / (1024**3), 1),
        "ram_used_pct": mem.percent,
        "ram_available_gb": round(mem.available / (1024**3), 1),
        "ollama_running": ollama_ok,
    }


register_tool(
    agent_name="system",
    schema={
        "name": "check_system_health",
        "description": "Check disk space, memory usage, and Ollama status",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    execute_fn=check_system_health
)
```

## tools/usaspending.py

USAspending.gov API tools. No authentication required.

```python
import httpx
from tools.base import register_tool

BASE_URL = "https://api.usaspending.gov/api/v2"


def search_spending(keyword: str = "", agency: str = "", limit: int = 10) -> dict:
    payload = {
        "filters": {
            "time_period": [{"start_date": "2025-01-01", "end_date": "2026-12-31"}],
        },
        "limit": min(limit, 100),
        "page": 1,
        "sort": "Award Amount",
        "order": "desc",
    }
    if keyword:
        payload["filters"]["keywords"] = [keyword]
    if agency:
        payload["filters"]["agencies"] = [
            {"type": "awarding", "tier": "toptier", "name": agency}
        ]

    resp = httpx.post(f"{BASE_URL}/search/spending_by_award/", json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    return {
        "total_results": data.get("page_metadata", {}).get("total", 0),
        "results": [
            {
                "award_id": r.get("Award ID"),
                "recipient": r.get("Recipient Name"),
                "amount": r.get("Award Amount"),
                "agency": r.get("Awarding Agency"),
                "description": (r.get("Description") or "")[:200],
                "date": r.get("Start Date"),
            }
            for r in data.get("results", [])[:limit]
        ],
    }


def get_agency_spending_summary() -> dict:
    resp = httpx.get(
        f"{BASE_URL}/references/toptier_agencies/",
        params={"sort": "obligated_amount", "order": "desc"},
        timeout=30
    )
    resp.raise_for_status()
    results = resp.json().get("results", [])[:15]
    return {
        "agencies": [
            {
                "name": r.get("agency_name"),
                "budget": r.get("budget_authority_amount"),
                "obligated": r.get("obligated_amount"),
                "percentage": r.get("percentage_of_total_budget_authority"),
            }
            for r in results
        ]
    }


register_tool(
    agent_name="research",
    schema={
        "name": "search_spending",
        "description": "Search federal spending awards by keyword, agency, or amount",
        "input_schema": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "Search keyword"},
                "agency": {"type": "string", "description": "Agency name filter"},
                "limit": {"type": "integer", "description": "Max results (default 10)"},
            },
            "required": []
        }
    },
    execute_fn=search_spending
)

register_tool(
    agent_name="research",
    schema={
        "name": "get_agency_spending_summary",
        "description": "Get spending summary for top federal agencies",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    execute_fn=get_agency_spending_summary
)
```

## state.py

Interface to thoth_state.db.

```python
import sqlite3
import json
import time
from config import STATE_DB


def _get_conn():
    conn = sqlite3.connect(str(STATE_DB))
    conn.row_factory = sqlite3.Row
    return conn


def start_cycle() -> int:
    conn = _get_conn()
    cur = conn.execute(
        "INSERT INTO task_log (task_type, task_name, status, started_at) VALUES (?, ?, ?, ?)",
        ("cycle", "decision_cycle", "running", time.time())
    )
    conn.commit()
    cycle_id = cur.lastrowid
    conn.close()
    return cycle_id


def finish_cycle(cycle_id: int, status: str = "success"):
    conn = _get_conn()
    conn.execute(
        "UPDATE task_log SET status=?, completed_at=? WHERE id=?",
        (status, time.time(), cycle_id)
    )
    conn.commit()
    conn.close()


def log_task(cycle_id: int, task_type: str, task_name: str, status: str,
             model_used: str = "", input_tokens: int = 0, output_tokens: int = 0,
             cost_usd: float = 0.0, result_summary: str = "", error_message: str = ""):
    conn = _get_conn()
    conn.execute(
        """INSERT INTO task_log
           (task_type, task_name, status, started_at, completed_at,
            token_cost, model_used, error_message, result_summary, metadata)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (task_type, task_name, status, time.time(), time.time(),
         cost_usd, model_used, error_message or None, result_summary or None,
         json.dumps({"input_tokens": input_tokens, "output_tokens": output_tokens,
                     "cycle_id": cycle_id}))
    )
    conn.commit()
    conn.close()


def log_cost(model: str, task_type: str, input_tokens: int, output_tokens: int,
             cost_usd: float, cached_tokens: int = 0):
    conn = _get_conn()
    conn.execute(
        """INSERT INTO cost_log (model, task_type, input_tokens, output_tokens, cost_usd, cached_tokens)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (model, task_type, input_tokens, output_tokens, cost_usd, cached_tokens)
    )
    conn.commit()
    conn.close()


def get_daily_cost() -> float:
    conn = _get_conn()
    row = conn.execute(
        "SELECT COALESCE(SUM(cost_usd), 0) FROM cost_log WHERE timestamp >= datetime('now', '-1 day')"
    ).fetchone()
    conn.close()
    return row[0]


def get_pending_escalations() -> list:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM escalation_queue WHERE status='pending' ORDER BY created_at"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_escalation(category: str, title: str, description: str,
                   priority: str = "normal", options: list = None,
                   recommendation: str = None):
    conn = _get_conn()
    conn.execute(
        """INSERT INTO escalation_queue (category, title, description, priority, options, recommendation)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (category, title, description, priority,
         json.dumps(options) if options else None, recommendation)
    )
    conn.commit()
    conn.close()
```

## memory.py

Interface to thoth_memory.db.

```python
import sqlite3
import json
import uuid
from config import MEMORY_DB


def _get_conn():
    conn = sqlite3.connect(str(MEMORY_DB))
    conn.row_factory = sqlite3.Row
    return conn


def store_knowledge(category: str, domain_tags: list, content: str,
                    source: str, confidence: float = 0.5,
                    expires_at: str = None, references: list = None) -> str:
    entry_id = str(uuid.uuid4())[:8]
    conn = _get_conn()
    conn.execute(
        """INSERT INTO knowledge (id, category, domain_tags, content, source, confidence, expires_at, references_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (entry_id, category, json.dumps(domain_tags), content, source,
         confidence, expires_at, json.dumps(references) if references else None)
    )
    conn.commit()
    conn.close()
    return entry_id


def recall_relevant(domain_tags: list = None, category: str = None,
                    limit: int = 10) -> list:
    conn = _get_conn()
    conditions = ["confidence > 0.1"]
    params = []

    if category:
        conditions.append("category = ?")
        params.append(category)

    if domain_tags:
        tag_conditions = []
        for tag in domain_tags:
            tag_conditions.append("domain_tags LIKE ?")
            params.append(f"%{tag}%")
        conditions.append(f"({' OR '.join(tag_conditions)})")

    conditions.append("(expires_at IS NULL OR expires_at > datetime('now'))")

    query = f"""SELECT * FROM knowledge
                WHERE {' AND '.join(conditions)}
                ORDER BY confidence DESC, created_at DESC
                LIMIT ?"""
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def store_research_prompt(prompt_text: str, priority: str = "important",
                          channel: str = None) -> int:
    conn = _get_conn()
    cur = conn.execute(
        """INSERT INTO research_prompts (prompt_text, priority, channel)
           VALUES (?, ?, ?)""",
        (prompt_text, priority, channel)
    )
    conn.commit()
    prompt_id = cur.lastrowid
    conn.close()
    return prompt_id


def get_pending_research() -> list:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM research_prompts WHERE status='pending' ORDER BY created_at"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
```

## calibration.py

Interface to thoth_calibration.db.

```python
import sqlite3
import time
from config import CALIBRATION_DB


def _get_conn():
    conn = sqlite3.connect(str(CALIBRATION_DB))
    conn.row_factory = sqlite3.Row
    return conn


def log_calibration_task(task_type: str, task_description: str,
                         self_success: bool, self_quality: float,
                         token_cost: float, time_seconds: float,
                         output_summary: str) -> int:
    conn = _get_conn()
    cur = conn.execute(
        """INSERT INTO calibration_tasks
           (task_type, task_description, self_assessed_success, self_assessed_quality,
            token_cost, time_seconds, output_summary)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (task_type, task_description, int(self_success), self_quality,
         token_cost, time_seconds, output_summary)
    )
    conn.commit()
    task_id = cur.lastrowid
    conn.close()
    return task_id


def get_calibration_matrix() -> list:
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM calibration_matrix").fetchall()
    conn.close()
    return [dict(r) for r in rows]
```

## models.py

Pydantic models for structured output validation.

```python
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
```

## coordinator.py

The main decision loop.

```python
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
                force_cloud=task.force_cloud,
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

    def _get_agent_prompt(self, agent_name: str) -> str:
        prompts = {
            "research": "You are a financial research agent. Use tools to gather data. Be concise.",
            "data": "You are a data processing agent. Clean and enrich data. Report anomalies.",
            "newsletter": "You are a financial newsletter writer. Every number must be sourced.",
            "system": "You are a system monitor. Check health and report issues briefly.",
        }
        return prompts.get(agent_name, "You are a helpful assistant.")
```

## discord_report.py

Report formatting. Prints to stdout for now — Discord integration comes later.

```python
from models import DailyReport


def format_report_text(report: DailyReport) -> str:
    lines = [f"**{report.status_line}**\n"]

    if report.metrics:
        lines.append("📊 **Metrics**")
        for k, v in report.metrics.items():
            lines.append(f"  {k}: {v}")
        lines.append("")

    if report.completed_tasks:
        lines.append(f"✅ **Completed** ({len(report.completed_tasks)})")
        for t in report.completed_tasks[:5]:
            lines.append(f"  • {t[:100]}")
        lines.append("")

    if report.failed_tasks:
        lines.append(f"❌ **Failed** ({len(report.failed_tasks)})")
        for t in report.failed_tasks[:5]:
            lines.append(f"  • {t[:100]}")

    return "\n".join(lines)


def send_report(report: DailyReport):
    text = format_report_text(report)
    print(text)
```

## main.py

Entry point.

```python
import sys
import time
import traceback
from coordinator import Coordinator


def run_once():
    coordinator = Coordinator()
    coordinator.run_cycle()


def run_loop(interval_seconds: int = 3600):
    print(f"Thoth starting — cycle interval: {interval_seconds}s")
    while True:
        try:
            run_once()
        except Exception as e:
            print(f"Cycle failed: {e}", file=sys.stderr)
            traceback.print_exc()
        time.sleep(interval_seconds)


if __name__ == "__main__":
    if "--loop" in sys.argv:
        interval = 3600
        for i, arg in enumerate(sys.argv):
            if arg == "--interval" and i + 1 < len(sys.argv):
                interval = int(sys.argv[i + 1])
        run_loop(interval)
    else:
        run_once()
```

## After creating all files, test with:

```bash
cd ~/thoth/core && python3 main.py
```

This should run one complete WAKE→ASSESS→PLAN→EXECUTE→REPORT cycle.