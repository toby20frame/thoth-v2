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

