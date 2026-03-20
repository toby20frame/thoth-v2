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

