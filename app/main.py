from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from app.proxy import forward_chat
from app.database import init_db, log_request
from app.stats import get_summary, get_latency_stats, get_cost_over_time, get_latency_over_time, get_model_breakdown
from app.alert import check_and_alert, get_todays_spend
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request
import os


app = FastAPI(title="LLMOps Monitor")



@app.on_event("startup")
async def startup():
    init_db()

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: list[Message]
    model: str = None

class ChatResponse(BaseModel):
    reply: str
    model: str
    latency_ms: float
    tokens: dict

templates = Jinja2Templates(directory="app/templates")

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={"request": request})

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        result = await forward_chat(
            [m.model_dump() for m in request.messages],
            request.model
        )
        # 👇 log on success
        log_request(
            model=result["model"],
            latency_ms=result["latency_ms"],
            tokens=result["tokens"],
            status="success"
        )
        await check_and_alert()
    except Exception as e:
        # 👇 log on failure too
        log_request(
            model=request.model or "mistral",
            latency_ms=0,
            tokens={},
            status="error"
        )
        raise HTTPException(status_code=502, detail=str(e) or repr(e))
        
    # Pull the reply text out of the Ollama response
    reply = result["response"]["choices"][0]["message"]["content"]

    return ChatResponse(
        reply=reply,
        model=result["model"],
        latency_ms=result["latency_ms"],
        tokens=result["tokens"],
    )

@app.get("/stats/summary")
async def stats_summary():
    return get_summary()

@app.get("/stats/latency")
async def stats_latency():
    return get_latency_stats()

@app.get("/stats/cost-over-time")
async def stats_cost_over_time():
    return get_cost_over_time()

@app.get("/stats/latency-over-time")
async def stats_latency_over_time():
    return get_latency_over_time()

@app.get("/stats/model-breakdown")
async def stats_model_breakdown():
    return get_model_breakdown()

@app.get("/stats/alert-status")
async def alert_status():
    spend     = get_todays_spend()
    threshold = float(os.getenv("SPEND_ALERT_THRESHOLD", "0.001"))
    return {
        "todays_spend":  spend,
        "threshold":     threshold,
        "exceeded":      spend >= threshold,
        "percent_used":  round((spend / threshold) * 100, 1) if threshold else 0,
    }