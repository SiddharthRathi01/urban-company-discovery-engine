# Discovery Engine – frontend

React + TypeScript + Vite. Full website: home, Overview (Feedback, Analysis, AI Evidence Log), Workflow and Ask questions.

## Run

From the project root (uses the bundled portable Node in `.node/` if there is one):

```
start-frontend.cmd
```

or, with Node 20.19+ installed: `cd frontend && npm install && npm run dev` → http://localhost:5173

| Script | Purpose |
|---|---|
| `npm run dev` | dev server on :5173 |
| `npm run typecheck` | TypeScript check |
| `npm run build` | type check + production build into `dist/` |
| `npm run preview` | serve the production build |

The dev server proxies `/api` to the FastAPI backend (`http://localhost:8000`, override with `VITE_API_TARGET`). Every screen reads its data from the API; nothing is hard-coded and no secrets are used.

## Structure

```
src/
  main.tsx, App.tsx            entry and routes (/, /overview/{feedback,analysis,evidence}, /workflow, /ask)
  api/                         fetch client (cached GET, upload) and response types
  hooks/useApi.ts              data hook with loading / error state
  layout/AppShell.tsx          sidebar + content frame (responsive)
  components/                  Backdrop, Header, FeatureCard, icons, ui (cards, KPIs, quotes), charts (SVG/CSS), CommentsDrawer
  pages/                       Home, FeedbackPage, AnalysisPage (+ analysis/ sections), EvidencePage, WorkflowPage, AskPage, NotFound
  styles/global.css, app.css   tokens + home screen, then shell / cards / charts / drawer
```

Dependencies: react, react-dom, react-router-dom and the self-hosted Plus Jakarta Sans font. Charts are hand-written SVG/CSS (no chart library).
Run everything with `start-app.cmd` in the project root (site + API on :8000).
