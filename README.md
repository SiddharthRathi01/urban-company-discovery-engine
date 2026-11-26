# Urban Company Discovery Engine

An AI-powered discovery engine that reads public customer feedback about Urban Company and turns it into evidence a product team can act on: what customers feel, the problems they raise, whether their words point to booking again, and which product opportunities could raise the share of customers who **complete another booking within 90 days**. Every finding links back to the real comment behind it.

[![Live app](https://img.shields.io/badge/Live%20app-urban--company--discovery--engine.vercel.app-0e7c7b?style=for-the-badge)](https://urban-company-discovery-engine.vercel.app)
[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/SiddharthRathi01/urban-company-discovery-engine/blob/main/notebook/Urban_Company_Discovery_Engine.ipynb)

## Explore the project
| | |
|---|---|
| **Live app** | [urban-company-discovery-engine.vercel.app](https://urban-company-discovery-engine.vercel.app): overview, analysis, AI Evidence Log, golden data set, workflow and Ask Questions |
| **AI Evidence Log** | [Urban_Company_AI_Evidence_Log.pdf](docs/Urban_Company_AI_Evidence_Log.pdf): sources, how the engine works, validation, safeguards and limitations |
| **Dataset** | [urban_company_reviews_master.csv](output/urban_company_reviews_master.csv): 2,527 public reviews, each with its source link |
| **Golden data set** | [golden_data_set.csv](golden/golden_data_set.csv): 20 comments labelled by hand to test the engine |
| **Runnable workflow** | [Colab notebook](notebook/Urban_Company_Discovery_Engine.ipynb): the six steps written out; press *Run all* |

## What the engine does
| Step | What happens | Result |
|---|---|---|
| **1 · Collect** | Public reviews and posts from Google Play, Reddit and two complaint sites | 3,788 records |
| **2 · Clean** | Duplicates, spam and off-topic posts removed; every review must have its own source page | 2,527 reviews |
| **3 · Read** | Each review is read for sentiment, the problem raised and a Return / Non-Return signal | 86.8% given a return reading |
| **4 · Group** | Problems and unmet needs are grouped into recurring themes | 5 themes, 14 unmet needs |
| **5 · Prioritise** | Opportunities are scored on reach, pain, evidence strength, link to leaving and impact | 9 ranked opportunities with a PM brief each |
| **6 · Prove** | Every finding links to verbatim quotes and their source; results are checked against a hand-labelled golden set | AI Evidence Log |

The live app also runs the engine on any CSV a visitor uploads (with an LLM on Cloudflare Workers AI) and answers questions about the feedback, each answer backed by quotes that are checked word for word. Visitors' files are analysed for that visit only and never stored.

## Key findings
- **Who comes back:** 1,119 reviews read as Return and 1,074 as Non-Return; 111 customers say it in their own words. These are readings of what customers wrote, not observed repeat-booking rates.
- **Top opportunities:**
  1. Quality, conduct and safety assurance (score 93)
  2. Arrival guarantee and proactive recovery (90)
  3. Human-reachable support with first-contact resolution (90)
- **Biggest theme:** service quality, professional conduct and trust appears in 51% of reviews, both as praise and as complaint.

## How the results were checked
- **Golden set:** 20 comments labelled by hand, then analysed by the engine: 16 full matches, 2 partial, 2 non-matches (sentiment 80% agreement, Return / Non-Return 90%).
- **Quotes:** all 370 quotes shown in the analysis appear word for word in the original review.
- **Sentiment:** a random re-read of 190 labels agreed on 184 (97%).
- **Bias:** complaint-site negativity and customers who leave silently are handled and explained in the AI Evidence Log.

## Built with
React and TypeScript (website), FastAPI (API), Cloudflare Workers AI (LLM for live analysis and answers), Vercel (hosting). Only public pages were used; no logged-in Urban Company pages or app data.

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
