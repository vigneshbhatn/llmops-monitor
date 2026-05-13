import httpx
import time
import os
from dotenv import load_dotenv

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OPENAI_API_KEY  = os.getenv("OPENAI_API_KEY", "")

async def forward_chat(messages: list, model: str = None):
    model = model or os.getenv("DEFAULT_MODEL", "mistral")

    headers = {"Content-Type": "application/json"}
    if OPENAI_API_KEY:
        base_url = "https://api.openai.com/v1"
        headers["Authorization"] = f"Bearer {OPENAI_API_KEY}"
        model = "gpt-3.5-turbo"  # fallback to cheapest OpenAI model
    else:
        base_url = OLLAMA_BASE_URL

    payload = {"model": model, "messages": messages}

    start = time.time()
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{base_url}/chat/completions",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()

    latency_ms = round((time.time() - start) * 1000, 2)
    data = response.json()

    return {
        "response":   data,
        "latency_ms": latency_ms,
        "model":      model,
        "tokens":     data.get("usage", {}),
    }