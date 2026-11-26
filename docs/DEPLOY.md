# Deploying to Vercel

The whole product is one Vercel project: the built website (static files) and the Python API (one serverless function, `api/index.py`).

## How the public site behaves
- The Urban Company analysis, the dataset, the **official golden set**, the notebook and the AI Evidence Log are files in the project. They are permanent and read-only.
- Anything a visitor uploads (a review CSV or a hand-labelled golden set) is analysed in a **temporary session**: the file is checked, read by the LLM a few comments at a time, and the result is kept only in that visitor's browser tab. Nothing is written to the server, nobody else can see it, and it is gone when the tab closes.
- `PUBLIC_MODE` is on by default. It switches off every endpoint that could store, replace or delete a file. Set `PUBLIC_MODE=0` only on your own computer if you want the older stored-upload endpoints.
- There is no per-visitor limit. The only guard is Cloudflare's own free daily allowance (10,000 neurons). The app's daily budget counter lives in the function's temporary folder, so it is not shared between function instances; when Cloudflare's allowance runs out, the AI features show a clear message until the next day (00:00 UTC).

## Steps
1. Put the project in a GitHub repository (the `.env` file is already git-ignored; never upload it).
2. In Vercel: **Add New → Project → import the repository**. Leave the framework as "Other". `vercel.json` already sets the build command, the output folder and the function.
3. In **Settings → Environment Variables** add `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN` (and optionally `CLOUDFLARE_MODEL`). These stay on the server; the website never sees them.
4. Deploy. The live address is https://urban-company-discovery-engine.vercel.app
5. Rebuild the AI Evidence Log so its links use that address, then redeploy:
   `SITE_URL=https://your-project.vercel.app .python\python.exe scripts\build_evidence_log.py`
6. Optional: for a one-click "Open in Colab" button, put the repository on GitHub and link
   `https://colab.research.google.com/github/<user>/<repo>/blob/main/notebook/Urban_Company_Discovery_Engine.ipynb`.

## Limits to know
- A function may run for at most 300 seconds (the Hobby plan maximum). Each AI request the site makes takes well under a minute, so a 300-review file is analysed as about 25 short requests.
- The function's disk is read-only except `/tmp`, which is cleared when the function restarts. That is why nothing is stored.
- Python functions are limited to 500 MB unzipped. The project is far below that.
- Not yet tested on Vercel itself (no account was available while building). The first deployment is the real test; the temporary-analysis flow has been tested locally with the live AI provider.
