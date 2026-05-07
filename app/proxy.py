import httpx
import time
import os
from dotenv import load_dotenv

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "mistral")

async def forward_chat(messages: list, model: str = None):
    model = model or DEFAULT_MODEL
    payload = {
        "model": model,
        "messages": messages,
    }

    start = time.time()

    async with httpx.AsyncClient(timeout=300.0) as client:
        response = await client.post(
            f"{OLLAMA_BASE_URL}/chat/completions",
            json=payload,
        )
        response.raise_for_status()

    latency_ms = round((time.time() - start) * 1000, 2)
    data = response.json()

    return {
        "response": data,
        "latency_ms": latency_ms,
        "model": model,
        "tokens": data.get("usage", {}),
    }