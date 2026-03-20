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

