from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from app.proxy import forward_chat
from app.database import init_db, log_request
from app.stats import get_summary, get_latency_stats, get_cost_over_time, get_latency_over_time, get_model_breakdown, get_agent_breakdown
from app.alert import check_and_alert, get_todays_spend
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
import time
import uuid
import httpx

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

def detect_agent(request: Request, body: dict = None) -> str:
    # 1. Check custom header
    agent = request.headers.get("x-agent-name")
    if agent:
        return agent.strip()
    
    # 2. Check query parameter
    agent = request.query_params.get("agent")
    if agent:
        return agent.strip()
    
    # 3. Check body parameter
    if body and isinstance(body, dict):
        agent = body.get("agent")
        if agent:
            return str(agent).strip()
            
    # 4. Check User-Agent
    user_agent = request.headers.get("user-agent", "").lower()
    if "antigravity" in user_agent:
        return "Antigravity"
    if "claude-code" in user_agent or "claude" in user_agent:
        return "Claude Code"
    if "openai" in user_agent:
        return "OpenAI SDK"
    if "anthropic" in user_agent:
        return "Anthropic SDK"
        
    # Default based on route path
    if request.url.path.endswith("/messages"):
        return "Claude Code"
        
    return "Unknown/Direct"

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
        # 👇 log on success with "Web UI" agent
        log_request(
            model=result["model"],
            latency_ms=result["latency_ms"],
            tokens=result["tokens"],
            status="success",
            agent="Web UI"
        )
        await check_and_alert()
    except Exception as e:
        # 👇 log on failure too
        log_request(
            model=request.model or "mistral",
            latency_ms=0,
            tokens={},
            status="error",
            agent="Web UI"
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

@app.post("/v1/chat/completions")
async def openai_chat_completions(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
        
    messages = body.get("messages", [])
    model = body.get("model")
    agent = detect_agent(request, body)
    
    try:
        result = await forward_chat(messages, model)
        log_request(
            model=result["model"],
            latency_ms=result["latency_ms"],
            tokens=result["tokens"],
            status="success",
            agent=agent
        )
        await check_and_alert()
        return result["response"]
    except Exception as e:
        log_request(
            model=model or "mistral",
            latency_ms=0,
            tokens={},
            status="error",
            agent=agent
        )
        raise HTTPException(status_code=502, detail=str(e) or repr(e))

@app.post("/v1/messages")
@app.post("/messages")
async def anthropic_messages(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
        
    agent = detect_agent(request, body)
    api_key = request.headers.get("x-api-key", "")
    
    # If the user has provided a real Anthropic API key, we can proxy directly to Anthropic.
    # Otherwise, translate it to OpenAI/Ollama format.
    if api_key and api_key != "not-needed":
        start_time = time.time()
        headers = {
            "x-api-key": api_key,
            "anthropic-version": request.headers.get("anthropic-version", "2023-06-01"),
            "content-type": "application/json"
        }
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    json=body,
                    headers=headers
                )
                response.raise_for_status()
                data = response.json()
                
            latency_ms = round((time.time() - start_time) * 1000, 2)
            
            usage = data.get("usage", {})
            prompt_tokens = usage.get("input_tokens", 0)
            completion_tokens = usage.get("output_tokens", 0)
            total_tokens = prompt_tokens + completion_tokens
            
            log_request(
                model=data.get("model", "claude-3"),
                latency_ms=latency_ms,
                tokens={
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens
                },
                status="success",
                agent=agent
            )
            await check_and_alert()
            return data
        except Exception as e:
            log_request(
                model=body.get("model", "claude-3"),
                latency_ms=0,
                tokens={},
                status="error",
                agent=agent
            )
            raise HTTPException(status_code=502, detail=str(e) or repr(e))
    else:
        # Translate Anthropic format to OpenAI format
        system_prompt = body.get("system")
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
            
        for msg in body.get("messages", []):
            role = msg.get("role")
            content = msg.get("content")
            if isinstance(content, list):
                text_parts = []
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        text_parts.append(part.get("text", ""))
                content_str = "\n".join(text_parts)
            else:
                content_str = str(content)
            messages.append({"role": role, "content": content_str})
            
        model = body.get("model")
        
        try:
            result = await forward_chat(messages, model)
            
            openai_response = result["response"]
            choices = openai_response.get("choices", [])
            reply_text = ""
            if choices:
                reply_text = choices[0].get("message", {}).get("content", "")
                
            prompt_tokens = result["tokens"].get("prompt_tokens", 0)
            completion_tokens = result["tokens"].get("completion_tokens", 0)
            total_tokens = result["tokens"].get("total_tokens", 0)
            
            log_request(
                model=result["model"],
                latency_ms=result["latency_ms"],
                tokens=result["tokens"],
                status="success",
                agent=agent
            )
            await check_and_alert()
            
            anthropic_response = {
                "id": f"msg_mock_{uuid.uuid4().hex[:16]}",
                "type": "message",
                "role": "assistant",
                "content": [
                    {
                        "type": "text",
                        "text": reply_text
                    }
                ],
                "model": result["model"],
                "stop_reason": "end_turn",
                "stop_sequence": None,
                "usage": {
                    "input_tokens": prompt_tokens,
                    "output_tokens": completion_tokens
                }
            }
            return anthropic_response
        except Exception as e:
            log_request(
                model=model or "mistral",
                latency_ms=0,
                tokens={},
                status="error",
                agent=agent
            )
            raise HTTPException(status_code=502, detail=str(e) or repr(e))

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

@app.get("/stats/agent-breakdown")
async def stats_agent_breakdown():
    return get_agent_breakdown()

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