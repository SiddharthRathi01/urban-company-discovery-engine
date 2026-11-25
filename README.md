# Urban Company Discovery Engine

An AI-powered discovery engine that reads public customer feedback about Urban Company and turns it into themes, a Return / Non-Return reading of every comment, and nine ranked product opportunities, each backed by real comments you can open at the source. The business metric it works towards: the share of customers who complete another booking within 90 days.

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/SiddharthRathi01/urban-company-discovery-engine/blob/main/notebook/Urban_Company_Discovery_Engine.ipynb)

## What is inside
| Folder | What it holds |
|---|---|
| `frontend/` | The website (React + TypeScript): overview, analysis, AI Evidence Log, golden data set, workflow, Ask Questions |
| `backend/`, `api/` | The API (FastAPI): the analysis, the live LLM engine, temporary analysis of visitors' files |
| `analysis/` | The analysis results the website reads (read-only) |
| `output/` | The dataset: 2,527 public reviews, each with its source link |
| `golden/` | The official hand-labelled golden set |
| `notebook/` | The runnable Colab notebook of the six-step workflow |
| `docs/` | The AI Evidence Log (PDF), backend notes and the deployment guide |
| `scripts/` | The collection, cleaning, analysis and report-building scripts |
| `tests/` | Automated tests |

## Run it on your computer
```
python -m pip install -r requirements-dev.txt
cd frontend && npm install && npm run build && cd ..
python -m uvicorn backend.api.main:app --port 8000
```
Open http://localhost:8000. To use the live AI features, copy `.env.example` to `.env` and add your Cloudflare Workers AI account ID and token (never commit `.env`).

## Deploy
See `docs/DEPLOY.md` (Vercel).
