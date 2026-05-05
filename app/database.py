import sqlite3
import os

DB_PATH = os.getenv("DB_PATH", "llmops.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS request_logs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT    NOT NULL,
            model       TEXT    NOT NULL,
            latency_ms  REAL    NOT NULL,
            prompt_tokens    INTEGER DEFAULT 0,
            completion_tokens INTEGER DEFAULT 0,
            total_tokens     INTEGER DEFAULT 0,
            estimated_cost   REAL    DEFAULT 0.0,
            status      TEXT    NOT NULL
        )
    """)
    conn.commit()
    conn.close()

# Hypothetical OpenAI-equivalent pricing (per 1000 tokens)
# Useful for showing "what this would cost on OpenAI"
COST_PER_1K = {
    "mistral":  {"prompt": 0.0002, "completion": 0.0002},
    "llama3":   {"prompt": 0.0002, "completion": 0.0002},
    "gemma2":   {"prompt": 0.0001, "completion": 0.0001},
    "default":  {"prompt": 0.0002, "completion": 0.0002},
}

def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    rates = COST_PER_1K.get(model, COST_PER_1K["default"])
    cost = (prompt_tokens / 1000 * rates["prompt"]) + \
           (completion_tokens / 1000 * rates["completion"])
    return round(cost, 6)

from datetime import datetime, timezone

def log_request(model: str, latency_ms: float, tokens: dict, status: str):
    prompt_tokens     = tokens.get("prompt_tokens", 0)
    completion_tokens = tokens.get("completion_tokens", 0)
    total_tokens      = tokens.get("total_tokens", 0)
    cost              = estimate_cost(model, prompt_tokens, completion_tokens)

    conn = get_connection()
    conn.execute("""
        INSERT INTO request_logs
            (timestamp, model, latency_ms, prompt_tokens,
             completion_tokens, total_tokens, estimated_cost, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now(timezone.utc).isoformat(),
        model, latency_ms,
        prompt_tokens, completion_tokens, total_tokens,
        cost, status
    ))
    conn.commit()
    conn.close()