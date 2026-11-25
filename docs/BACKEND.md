# Customer Discovery Engine – Step 2 backend and analysis

Product analysed: **Urban Company**. Target metric: % of customers who complete another booking within 90 days.
Scope of this document: the precomputed analysis (`analysis/`), the read-only API (`backend/api/`), the CSV-upload foundation and the tests.
Not in scope (Step 3 and later): Golden Set, human labels, accuracy/agreement tests, final frontend, deployment, LLM analysis of uploads.

## 1. How the analysis was produced (read this first)

* Input: `output/urban_company_reviews_master.csv` – 2,069 reviews, 16 columns. 214 Insta Help reviews were removed from the Master sheet and CSV before analysis
  (kept, with full text, on the `Excluded Records` sheet of the workbook). Counts of the removal are in `analysis/overview.json` (`dataset.insta_help_*`).
* Method: **deterministic phrase rules** (23 issue codes, return-behaviour classes, alternatives, 14 unmet-need types) applied to title + text, then the matched
  text was **read and curated by an analyst (Claude)**: return classes, alternatives, triggers, household and discovery evidence use hand-vetted review lists.
  All counts are computed in code; every quote is verified to be verbatim in the review text.
* **No LLM produced these results.** Cloudflare Workers AI (section 8) powers the *live* features only: analysing uploaded CSVs and writing Ask answers. The precomputed Urban Company analysis was never replaced by AI-generated numbers.
* **Not human-validated.** Rule precision was spot-checked (6–8 random matches per code; about 75–100 %); formal validation is Step 3.
* Themes are multi-label: a review counts once in each theme it touches, so theme counts overlap and must not be added.

Rebuild (never edits the master):

```
.python/python.exe scripts/step2_tag_all.py      # rule coding -> raw/step2_tagged.pkl
.python/python.exe scripts/build_analysis.py     # -> analysis/*.json
```

## 2. Precomputed files (`analysis/`) – source of truth

| File | Content | Stable IDs |
|---|---|---|
| `overview.json` | dataset facts, sentiment/rating, headline metrics, method | – |
| `themes.json` | ≤5 themes: definition, count, % of dataset, sentiment, subthemes, source split, quotes, interpretation, overlap matrix, counting method | T1–T5, `T1.cancelled` |
| `findings.json` | top 3 findings with volume, impact, repeat-booking link, evidence | F1–F3 |
| `questions.json` | answers to the 8 assignment questions with evidence strength and gaps | Q1–Q8 |
| `behaviour.json` | Explicit Return / Explicit Non-Return / Behavioural Signal / Insufficient Evidence, patterns, comparison | class names |
| `alternatives.json` | alternative types; reported use vs considering vs general separated; WhatsApp/community finding | A1–A4 |
| `segments.json` | by service category, city, source, household type, discovery channel, booking trigger – all with sample sizes | `CAT_*`, `CITY_*`, `SRC_*`, `HH01`, `DC01`, `TRG01` |
| `unmet_needs.json` | 14 unmet needs with frequency, evidence, alternatives, return relevance, precision estimate | N01–N14 |
| `opportunities.json` | 9 prioritised opportunities with scoring formula, hypotheses and success metrics | O1–O9 |
| `evidence.json` | 330 verified quotes: review id, original id, source, URL, date, rating, full review text, what each supports | EV001… |
| `limitations.json` | dataset biases and method limits | – |
| `reviews.json` | all 2,069 reviews with their theme / issue / need / alternative / return labels | `record_id` (e.g. `GP-0245`) |
| `trust.json` | workflow stages, collection funnel, source coverage vs the brief, bias handling, validation numbers, golden-set status (not run) | S1–S8 |
| `manifest.json` | generation time, master-file SHA-256, file sizes, ID scheme | – |

Every file carries `schema_version`, `generated_at` and `dataset_reviews`. Evidence fields are customer-reported; fields named `*_hypothesis`, the impact
judgement and the success metrics in `opportunities.json` are recommendations, not findings.

## 3. Running the API

```
.python/python.exe -m pip install -r requirements.txt
.python/python.exe -m uvicorn backend.api.main:app --port 8000        # docs at http://localhost:8000/docs
.python/python.exe -m pytest tests -q
```

Environment variables (all optional; see `backend/api/settings.py`): `PRECOMPUTED_ANALYSIS_DIR`, `UPLOAD_DIR`, `MASTER_CSV`, `CORS_ORIGINS`, `LOG_LEVEL`,
`MAX_UPLOAD_MB` (10), `MAX_UPLOAD_ROWS` (20000), `UPLOAD_PROCESSOR` (default `cloudflare` when credentials are set, else `none`). No API key is needed for the precomputed analysis. The precomputed files are loaded
into memory at start-up and the API never writes to `analysis/` or `output/`.

Architecture: `main.py` (app, CORS, request log with `X-Request-ID`, error handlers) → `routers/analysis.py`, `routers/reviews.py`, `routers/uploads.py` →
`store.py` (read-only cached JSON access, derived indexes) and `uploads/` (`validator.py` pure validation, `storage.py` file storage and jobs, `processor.py` plug-in point).

### Response format

* Success: `{"data": …, "meta": {…}}`. `meta.source` is `"precomputed"`.
* Lists: `meta.page`, `page_size` (1–200, default 25), `total`, `total_pages`. Out-of-range page → 404 `page_out_of_range`.
* Errors: `{"error": {"code", "message", "details"}}` – codes such as `invalid_filter` (422, details list the allowed values), `invalid_request` (422),
  `<kind>_not_found` (404), `upload_rejected` (422/413/415), `duplicate_upload` (409), `analysis_unavailable` (503), `internal_error` (500).
* Detail endpoints expand referenced quotes into `data.evidence_quotes` (turn off with `?expand_evidence=false`).

### Endpoints (prefix `/api/v1`, plus `GET /health`)

| Endpoint | Purpose / filters |
|---|---|
| `GET /overview` | dashboard metrics |
| `GET /meta`, `GET /limitations` | dataset metadata, method, biases |
| `GET /themes`, `/themes/{T1..T5}` | theme summaries (meta has counting method and overlap matrix) / detail with review ids and quotes |
| `GET /findings`, `/findings/{F1..F3}` | top findings |
| `GET /questions`, `/questions/{Q1..Q8}` | the eight discovery questions |
| `GET /behaviour`, `/behaviour/classes/{explicit-return \| explicit-non-return \| behavioural-signal \| insufficient-evidence}` | return / non-return analysis and comparison |
| `GET /alternatives`, `/alternatives/{A1..A4}` | alternatives (reported vs general separated) |
| `GET /segments`, `/segments/{dimension}?min_n=`, `/segments/{dimension}/{segment_id}` | dimensions: `service_category, city, source, household_type, discovery_channel, booking_triggers` |
| `GET /unmet-needs?min_reviews=&linked_opportunity=`, `/unmet-needs/{N01..N14}` | unmet needs |
| `GET /opportunities?priority=High,Medium&theme=T3`, `/opportunities/{O1..O9}` | prioritised opportunities |
| `GET /llm/status`, `GET /llm/usage` | provider configuration (no secrets) and tracked usage: requests, failures, input/output tokens, neurons, time |
| `POST /llm/analyse-review` | analyse one review (sentiment, themes, problem, verbatim quote) |
| `GET /ask/answer?q=` | grounded answer written by Cloudflare Workers AI from retrieved reviews, with verified citations and usage |
| `GET /trust` | workflow stages, funnel, validation, bias handling, golden-set status (feeds the Workflow and AI Evidence Log screens) |
| `GET /mood?by=source\|theme\|issue\|category\|city\|return_class&min_n=&sort=` | sentiment mix per group, for the charts |
| `GET /ask?q=` | closest analysed question + three real reviews containing the words (keyword search, **not** an LLM) |
| `GET /evidence?theme=&supports=opportunity:O1&source=&sentiment=&review_id=&q=` , `/evidence/{EVnnn}` | verified quotes; `supports` is a prefix such as `finding:F1`, `theme:T3`, `question:Q4` |
| `GET /reviews?source=&sentiment=&theme=&return_class=&category=&city=&issue=&unmet_need=&alternative=&opportunity=&rating_min=&rating_max=&date_from=&date_to=&q=&sort=&order=&include_text=` , `/reviews/{record_id}` | original reviews with source, URL, date; detail includes the quotes taken from the review |

## 4. CSV upload and analysis

`POST /uploads` (multipart `file`), `GET /uploads`, `GET /uploads/{id}`, `GET /uploads/{id}/validation`, `POST /uploads/{id}/process[?force=true]`, `GET /uploads/{id}/job`,
`GET /uploads/{id}/analysis`, `GET /uploads/{id}/analysis/reviews?theme=&sentiment=`, `DELETE /uploads/{id}`.

* Accepts `.csv` only (UTF-8, comma/semicolon/tab/pipe delimiter, ≤10 MB, ≤20,000 rows). Required: a review-text column (aliases `review_text, text, review, content, body, comment, feedback…`).
  Optional (auto-mapped): `review_id, review_title, platform, source_url, review_date, rating, reviewer, service_category, city`.
* File-level rejection (422/413/415) with clear codes: `unsupported_file_type, unsupported_content_type, empty_file, not_text_csv, invalid_encoding, duplicate_columns,
  missing_required_column, too_many_rows, no_valid_rows, malformed_csv, file_too_large`.
* Row-level: rejected – `missing_review_text, review_text_too_short/long, column_count_mismatch, duplicate_in_file, duplicate_review_id, already_in_approved_dataset`;
  warning (value dropped, row kept) – `invalid_rating, invalid_date, invalid_url`. Each issue has line number, code, message and field; totals are exact, stored issues are capped at 200.
* Storage: `uploads/<upload_id>/` (original bytes, `accepted.csv`, `validation.json`, `upload.json`, `job.json`, `analysis/analysis.json`, `analysis/reviews.json`) – separate from `output/` and `analysis/`.
  Identical files are refused (409). Uploaded data can never change the precomputed Urban Company analysis (tests assert the analysis files stay byte-identical).
* `POST /uploads/{id}/process` starts a **background job** (`queued -> running -> completed | failed`, or `not_configured` without credentials) with live `progress` (phase, done/total, message)
  and, when finished, `usage`. One analysis runs at a time. If saved results exist the call returns them (`reused_saved_results: true`) with **zero** LLM calls; `force=true` re-runs
  (identical prompts are still served from the response cache). Jobs left running by a stopped server are marked failed at start-up.
* Processors are pluggable (`backend/api/uploads/processor.py`): `cloudflare` (default when credentials are set) and `none`.

## 5. Tests (`tests/`, 65 offline + 2 opt-in live)

* `test_analysis_data.py` – master is 2,069 rows × 16 columns with no Insta Help and no removed columns; manifest hash matches the master; `reviews.json` equals the master; every one of the 330
  quotes is verbatim in its review and matches source, URL and date; every evidence and review reference resolves; ≤5 themes; counts consistent; behaviour classes partition the dataset; structure of findings, opportunities, questions.
* `test_api.py` – envelope, pagination, filters, sorting, detail expansion, error codes, traceability from evidence → review → URL.
* `test_uploads.py` – valid/invalid uploads, row-level issues, duplicates (in file, id, approved dataset, whole file), size limit, storage separation, job status, analysis untouched, plug-in processor and failure containment.

## 6. Known limitations

See `analysis/limitations.json` (served at `/api/v1/limitations`): complaint-site negativity, Google Play dominance (72 %), missing city (91 %) and category (61 %), only 73 explicit return/non-return statements,
Reddit text is posts only and its permalinks are not machine-verified, excluded sources (Apple App Store, older complaint-site entries), rule-based coding not human-validated.

## 7. Website (`frontend/`) and running everything

React + TypeScript + Vite, in our own design (midnight navy, glass cards, lavender / orange / blue light). The blueprint follows the reference discovery-engine site:
home hub with three entries → Overview (Feedback, Analysis, AI Evidence Log) → workflow → ask questions. All numbers, charts and quotes come from the API; nothing is hard-coded.

| Screen | Route | Content |
|---|---|---|
| Home | `/` | three entry cards |
| Feedback | `/overview/feedback` | dataset status, KPIs, generated brief, mood by source / problem area / category / city |
| Analysis | `/overview/analysis` | ranked opportunities with score breakdown and real comments, bubble chart, compare, table, recurring themes, return vs non-return, alternatives, segment heat grids, unmet needs |
| AI Evidence Log | `/overview/evidence` | funnel, sources and brief coverage, both biases, validation numbers, follow-one-comment, golden-set status, limits, CSV upload test |
| Workflow | `/workflow` | eight pipeline steps, method honesty, the eight questions, what is not built yet |
| Ask questions | `/ask` | eight analysed questions or free text, with three real comments each |

Run:

```
start-app.cmd                         # builds the website if needed and serves site + API on http://localhost:8000
start-frontend.cmd                    # development: hot-reload site on http://localhost:5173 (needs the API on :8000)
```

When `frontend/dist` exists the API serves it (override with `FRONTEND_DIST`); `/api/*`, `/docs` and `/health` keep their JSON behaviour.

## 8. Cloudflare Workers AI (the only LLM provider)

* **Config** (backend only, `.env` is git-ignored; see `.env.example`): `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN`, optional `CLOUDFLARE_MODEL` (default `@cf/google/gemma-4-26b-a4b-it`),
  `CLOUDFLARE_DAILY_NEURON_BUDGET` (default 9000 of the free 10,000/day), `MAX_ANALYSIS_REVIEWS` (default 300 per upload), `CLOUDFLARE_CONCURRENCY` (default 3), `UPLOAD_BATCH_SIZE` (6).
  The token is never sent to the browser, logged, written to the ledger or included in error messages (it is redacted even if Cloudflare echoes it).
* **Client** (`backend/llm.py`): REST call, JSON-mode helper with schema validation, retries for 429/5xx/timeouts, clear fatal errors, a disk cache (`llm_data/cache`) so identical requests are never paid twice,
  and a daily neuron budget guard. The model is a reasoning model; hidden "thinking" is switched off (`chat_template_kwargs.enable_thinking=false`), which cut a test call from 248 to 33 output tokens (7.3 -> 1.5 neurons).
* **Usage ledger** (`llm_data/usage.jsonl`, summarised by `GET /llm/usage`): per request purpose, input tokens, output tokens, neurons (from Cloudflare's `usage.neurons` / `cf-ai-neurons` header), seconds, status.
* **CSV analysis** (`backend/csv_analysis.py`): (1) per-review extraction in batches (sentiment, 1-2 theme labels, problem, positive, one quote); (2) the model groups labels into at most five themes;
  (3) the model writes insights and opportunities from computed statistics and verbatim quotes. **Counts, percentages and sentiment totals are computed in code.** Original review ids and source URLs are preserved;
  a quote that is not verbatim in its review is replaced by the start of the review itself; unverifiable citations are dropped; generated text containing digits is dropped; opportunities are labelled hypotheses.
  Results are saved to `uploads/<id>/analysis/`, so the dashboard reads them with no LLM call. Files above `MAX_ANALYSIS_REVIEWS` rows are truncated and the result says how many rows were not analysed.
* **Ask** (`GET /ask/answer`): retrieval is the existing keyword search; the model answers only from the retrieved reviews and must cite them; each citation is verified verbatim; answers are cached.
* **Batch pipeline** (`backend/pipeline.py`, `python -m backend.run_analysis check|run|status`) now uses the same client. It is not used for the website data.
* **Live tests:** `set RUN_LIVE_LLM_TESTS=1` then `python -m pytest tests/test_live_cloudflare.py -s` (about 110-130 neurons).

## 9. Return / Non-Return classification (revision 2) and the golden set

**Classification.** Every review is placed as **Return**, **Non-Return** or **Insufficient Evidence**, with a *basis* (how it was decided) and a *confidence*:
`Stated` (first person: repeat use, will book again, will not return, switched; high), `Signalled` (advises others against the app, switching, distrust, or recommends with trust; medium),
`Inferred` (sentiment decides: Positive -> Return, Negative -> Non-Return; Mixed/Neutral only when the star rating is clearly 4-5 or 1-2; a contradiction stays Insufficient; medium when sentiment and rating agree, else low).
Result on the current dataset: 86.8% classified (target 70%): Return 1,119, Non-Return 1,074, Insufficient 334; basis Stated 111, Signalled 747, Inferred 1,335.
These are **predictions from public text**, not observed rebooking. Comparisons that use Inferred labels partly restate sentiment, so the Stated + Signalled groups are shown as the stronger evidence.
Rules: `scripts/step2_behaviour.py` (website data) and `backend/return_class.py` (live engine); a test keeps them identical. Filters: `/reviews?return_class=&return_basis=&return_confidence=`.

**Live engine.** The extraction prompt asks the model for `return_signal` (will_return / will_not_return / warns_others / recommends / none); the class is then decided in code with the same rules.
Uploaded-CSV analysis therefore reports `return_behaviour` too.

**Golden set** (`/api/v1/golden`): `POST /golden` (file + optional `mapping` JSON + `name`) validates a hand-labelled CSV (text, plus your sentiment and/or Return / Non-Return label, optional problem label, rating, URL);
`POST /golden/{id}/evaluate` runs the engine in the background; `GET /golden/{id}/evaluation|rows|job`; `POST /golden/{id}/primary` chooses the set shown on the AI Evidence Log; `DELETE /golden/{id}`.
Metrics: sentiment and Return/Non-Return agreement, Cohen's kappa, confusion matrices, and per-row Full / Partial / Non-match. Stored in `golden/` (a deliverable, not git-ignored).
No golden set has been uploaded yet, so **no accuracy figure is claimed**; agreement with labels is an accuracy estimate only if the set is representative and labelled independently of the engine.

**Data update.** A further random sample of detailed 4-5 star Google Play reviews was added (`scripts/collect_play_positive2.py`); existing record IDs are unchanged (stage B keeps IDs stable).
