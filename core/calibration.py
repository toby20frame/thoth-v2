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

