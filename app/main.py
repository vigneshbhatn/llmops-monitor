from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from app.proxy import forward_chat

app = FastAPI(title="LLMOps Monitor")

class ChatRequest(BaseModel):
    messages: list[dict]
    model: str = None

class ChatResponse(BaseModel):
    reply: str
    model: str
    latency_ms: float
    tokens: dict

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        result = await forward_chat(request.messages, request.model)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

    # Pull the reply text out of the Ollama response
    reply = result["response"]["choices"][0]["message"]["content"]

    return ChatResponse(
        reply=reply,
        model=result["model"],
        latency_ms=result["latency_ms"],
        tokens=result["tokens"],
    )