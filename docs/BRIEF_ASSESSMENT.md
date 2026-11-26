# Does the engine do what the brief asks? (assessment, 26 Nov 2026)

Brief (Part 1): build an AI-powered discovery engine that analyses public feedback at scale, answers eight customer-discovery questions, accounts for two biases,
goes beyond sentiment to identify and compare opportunity areas that could move the 90-day repeat-booking metric, and shows how it was validated (AI Evidence Log).

| Requirement | Status | Detail |
|---|---|---|
| Gather permitted public feedback | Mostly | 2,527 traceable reviews: Google Play 1,950, Reddit posts 251, PissedConsumer 165, ConsumerComplaints.in 161. No logged-in Urban Company pages were used. Not covered: Apple App Store (collected, left out because there is no page per review), Trustpilot (blocked), YouTube comments, other social media, shareholder letters and earnings-call transcripts, Reddit comments. The brief lists these as examples ("such as"). |
| AI-powered analysis at scale | Yes | The live engine (LLM on Cloudflare Workers AI) analyses any uploaded CSV: sentiment, themes, Return / Non-Return, insights, opportunities, verified quotes, saved results and usage tracking (measured: about 4.6 neurons per review plus about 78 fixed). The Urban Company dataset itself was read with phrase rules plus AI-assisted analyst review, with every count computed in code. |
| Answer the eight questions | Yes | All eight answered with evidence and an evidence-strength rating (short AI summary plus the full analysis and real quotes). Thinnest: how customers decide and when (Q2), household type and discovery channel (Q7); WhatsApp / neighbour networks leave little trace in public reviews (Q5). |
| Account for negative-voice bias and silent churn | Yes | Sentiment by source, pooled vs equal-weight themes, positive Play reviews added; every review placed as Return / Non-Return / Insufficient Evidence with basis and confidence. Customers who never wrote cannot be seen in public text; first-party booking data is the remedy. |
| Identify, quantify and compare opportunity areas | Yes | Nine scored opportunities, each with a product-manager brief (problem, proposal, effort, confidence, recommendation). The link to the 90-day repeat rate is a hypothesis; cohort data would measure it. |
| Show how themes and insights were produced | Yes | Workflow page, runnable Colab notebook, method text, evidence behind every claim. |
| Validate quality (AI Evidence Log) | Yes | AI Evidence Log (PDF, also on the Evidence page): sentiment spot-check 184/190 (97%), 370/370 quotes verified word for word, 20-comment hand-labelled golden set (16 full, 2 partial, 2 non-match; sentiment 80%, Return / Non-Return 90%), 71 automated tests. |

## Deployment readiness (Vercel)
Done: the official golden set and the Urban Company files are read-only; visitors' own files (review CSVs and golden sets) are analysed in a temporary session in short requests and kept only in their browser tab, never stored; no other visitor's file can be seen; `vercel.json`, `api/index.py`, split requirements and `docs/DEPLOY.md` are in place; 75 automated tests; the temporary flow was run end to end with the live AI provider.
Deployed: the site is live at https://urban-company-discovery-engine.vercel.app from the public GitHub repository (every push to `main` redeploys it), the Cloudflare keys are Vercel environment variables, and the Evidence Log links to the live address. Checked live: every page, the Ask page, a visitor's temporary upload and golden-set evaluation, and all four downloads.
