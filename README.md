# TraceWatch — LLM Observability Proxy

> A production-grade proxy and dashboard that tracks token usage, latency, and cost across any LLM — local or cloud. Drop it between your app and your model. See everything.

![Dashboard Preview](assets/dashboard-preview.png)

---

## What it does

Most teams using LLMs in production have no visibility into what's actually happening — how many tokens each request burns, which model is slow, or how fast costs are accumulating. TraceWatch fixes that.

It sits as a transparent proxy between your code and your LLM. Every request flows through it, gets measured, and appears on a live dashboard — no changes needed to your application logic.

```
Your app / agent
      │
      ▼
┌─────────────┐      logs to SQLite
│  TraceWatch │ ──────────────────────► Dashboard
│   (proxy)   │
└─────────────┘
      │
      ▼
 Ollama / OpenAI
```

---

## Features

- **Transparent proxy** — OpenAI-compatible (`/v1/chat/completions`) and Anthropic-compatible (`/v1/messages`) endpoints; zero changes to your agent or app code
- **Real-time dashboard** — live metric cards, latency trend charts (p50/p95), daily cost line chart, and per-model breakdown table
- **Token & cost tracking** — logs prompt tokens, completion tokens, and hypothetical OpenAI-equivalent cost on every request
- **Spend alerting** — fires a webhook when daily spend crosses a configurable threshold
- **Multi-agent support** — tracks Antigravity, Claude Code, and any OpenAI SDK-based agent as separate sources
- **Local-first** — works with Ollama (Mistral, Llama 3, Gemma 2) out of the box; falls back to OpenAI when a key is set
- **Docker + Railway deploy** — one command to run locally, one click to ship

---

## Tech stack

| Layer | Tech |
|---|---|
| Proxy & API | Python, FastAPI, httpx |
| Storage | SQLite |
| Dashboard | HTML, Chart.js |
| Local LLMs | Ollama (Mistral, Llama 3, Gemma 2) |
| Alerting | Webhook (webhook.site / Slack / custom) |
| Deployment | Docker, Railway |

---

## Getting started

### Prerequisites

- Python 3.11+
- [Ollama](https://ollama.com) installed and running
- Docker (optional, for deployment)

### 1. Clone and install

```bash
git clone https://github.com/yourusername/tracewatch.git
cd tracewatch
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

```env
# Local LLM (default)
OLLAMA_BASE_URL=http://localhost:11434/v1
DEFAULT_MODEL=mistral

# OpenAI fallback (leave blank to use Ollama)
OPENAI_API_KEY=

# Spend alerting
SPEND_ALERT_THRESHOLD=0.01
WEBHOOK_URL=https://webhook.site/your-unique-url
```

### 3. Pull a model and start Ollama

```bash
ollama pull mistral
ollama serve
```

### 4. Run TraceWatch

```bash
uvicorn app.main:app --reload --port 8000
```

Open [http://localhost:8000](http://localhost:8000) — the dashboard loads immediately.

---

## Usage

### Chat UI

Visit `http://localhost:8000` to use the built-in chat interface. Select a model from the dropdown, send a message, and watch token counts and latency appear inline under each reply.

### API

Send requests directly to the proxy:

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mistral",
    "messages": [{"role": "user", "content": "Explain RAG in one sentence."}]
  }'
```

### Connect your agent

**Any OpenAI SDK agent** — change two lines:

```python
from openai import OpenAI

client = OpenAI(
    api_key="not-needed",
    base_url="http://localhost:8000/v1",
)
```

**Antigravity** — in Settings → Model Provider:
```
Base URL:  http://localhost:8000/v1
API Key:   not-needed
Model:     mistral
```

**Claude Code:**
```bash
export ANTHROPIC_BASE_URL=http://localhost:8000
export ANTHROPIC_API_KEY=not-needed
```

---

## Dashboard

| Metric | Description |
|---|---|
| Total requests | All successful calls through the proxy |
| Avg latency | Mean response time across all requests |
| Total tokens | Cumulative token usage |
| Est. cost | Hypothetical OpenAI-equivalent spend |
| p50 / p95 latency | Median and worst-case response times |
| Daily spend bar | Today's usage vs configured threshold |
| Model breakdown | Per-model requests, latency, and cost |

---

## Stats API

All metrics are available as JSON endpoints:

```
GET /stats/summary           — total requests, avg latency, total cost, top model
GET /stats/latency           — p50, p95, min, max latency
GET /stats/cost-over-time    — daily cost and request count
GET /stats/latency-over-time — daily avg and max latency
GET /stats/model-breakdown   — per-model cost, requests, latency
GET /stats/agent-breakdown   — per-agent cost, requests, tokens
GET /stats/alert-status      — today's spend vs threshold
```

---

## Docker

```bash
# Build
docker build -t tracewatch .

# Run
docker run -p 8000:8000 \
  -e OPENAI_API_KEY=your_key \
  -e SPEND_ALERT_THRESHOLD=0.01 \
  tracewatch
```

---

## Deploy to Railway

1. Push to GitHub
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub
3. Add environment variables in the Railway dashboard
4. Generate a public domain under Settings → Networking

Your live URL will be something like `tracewatch.up.railway.app`.

---

## Project structure

```
tracewatch/
├── app/
│   ├── main.py          # FastAPI app, routes
│   ├── proxy.py         # LLM forwarding logic
│   ├── database.py      # SQLite schema, logging, cost estimation
│   ├── stats.py         # Aggregation queries
│   ├── alerts.py        # Spend threshold + webhook
│   └── templates/
│       └── index.html   # Dashboard + chat UI
├── Dockerfile
├── requirements.txt
└── .env.example
```

---

## Roadmap

- [ ] Streaming response support
- [ ] Per-session token budgets
- [ ] Slack alert integration
- [ ] Multi-user support with API keys
- [ ] Export logs as CSV

---

## License

MIT
