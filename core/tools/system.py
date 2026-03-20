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

