# FinSight Planner — Deployment Guide

**Financial Planning & Scenario Intelligence** · Phynapse (Applied AI Consulting & Engineering)

> All data is synthetic (fictional company **Asteron Group**). Portfolio decision-support demo, not an accounting system, ERP, or audited reporting source.

---

## 1. Overview

| Component | Stack | Default Port |
|---|---|---|
| Backend API | FastAPI + Uvicorn (Python 3.11+) | 8000 |
| Frontend | React + Vite (Node 18+) | 5173 |
| Data | Read-only CSV/JSON under `data/` | — |

Core principle: **calculate with deterministic financial models, explain with AI.** Every figure comes from Python/Pandas; the optional LLM only turns questions into a validated analysis plan and rewrites computed evidence into prose. Any figure it produces that is not in the evidence is rejected.

---

## 2. Prerequisites

- Python **3.11+** (verified on 3.14)
- Node.js **18+** and npm
- Git (optional)

---

## 3. Configuration

Copy the example env file and edit values:

```bash
cp .env.example backend/.env
```

| Variable | Required | Default | Description |
|---|---|---|---|
| `LLM_BASE_URL` | No | `https://api.openai.com/v1` | OpenAI-compatible endpoint |
| `LLM_API_KEY` | No | — | If unset/placeholder, app runs in deterministic mode |
| `LLM_MODEL` | No | `gpt-4` | Model name |
| `LLM_TIMEOUT` | No | `30` | Seconds |
| `API_HOST` | No | `0.0.0.0` | Bind address |
| `API_PORT` | No | `8000` | Backend port |
| `DEBUG` | No | `false` | Debug logging |
| `DATA_DIR` | No | `../data` | Data directory (relative to `backend/`) |

Keys stay server-side and are never returned by the API. Responses state whether the explanation came from `llm` or `deterministic_fallback`.

---

## 4. Backend Deployment

```bash
cd backend
python -m venv venv
# Windows
venv\Scripts\activate
# Unix
source venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- API: `http://<host>:8000/`
- Swagger docs: `http://<host>:8000/docs`
- Health check: `GET /api/health`

For production, run behind a reverse proxy (nginx/Caddy) with HTTPS and a process manager (systemd/supervisor). CORS origins are restricted to `localhost:5173` by default — update `app/main.py` `allow_origins` for your deployed frontend URL.

---

## 5. Frontend Deployment

```bash
cd frontend
npm install
npm run build        # type-check + production bundle -> dist/
npm run preview      # optional local preview on :4173
```

Serve the `frontend/dist/` directory with any static host (nginx, Vercel, Netlify, S3+CloudFront).

Point the frontend at your API by setting `VITE_API_URL` before building:

```bash
# Unix
VITE_API_URL=https://api.example.com npm run build
# Windows PowerShell
$env:VITE_API_URL="https://api.example.com"; npm run build
```

---

## 6. Verification

```bash
# Backend tests (no network/LLM credits required)
cd backend && python -m pytest -v

# Frontend type check + build
cd frontend && npm run build
```

Expected: 96 backend tests pass; frontend build succeeds.

---

## 7. Quick Start (local)

```bash
# Terminal 1
cd backend && venv\Scripts\activate && uvicorn app.main:app --reload

# Terminal 2
cd frontend && npm run dev
```

Open `http://localhost:5173` (expects API on `:8000`).

---

## 8. Notes

- Synthetic, sparse data (13 sampled actual months; budget/forecast partial).
- Scenarios and evidence are held in memory; no authentication or persistence.
- See `docs/` for architecture, financial model, data model, scenario methodology, AI architecture, testing, limitations, roadmap.

---

## License / Disclaimer

MIT. For demonstration and education only; not financial advice; not audited. All names and data are fictional.