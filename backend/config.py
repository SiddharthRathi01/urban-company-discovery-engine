"""Backend configuration. Cloudflare Workers AI is the ONLY LLM provider.

The API token is read ONLY from the environment (CLOUDFLARE_API_TOKEN), optionally loaded from the git-ignored .env file.
It is never written to outputs, logs, usage ledgers or the manifest, and is never sent to or exposed by the frontend."""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)
except ImportError:  # python-dotenv is optional; real environment variables still work
    pass

ROOT = Path(__file__).resolve().parent.parent
MASTER_CSV = ROOT / "output" / "urban_company_reviews_master.csv"
ANALYSIS_DIR = Path(os.environ.get("ANALYSIS_DIR", ROOT / "analysis_llm"))   # batch-pipeline output; precomputed website results live in analysis/
LLM_DATA_DIR = Path(os.environ.get("LLM_DATA_DIR") or ("/tmp/llm_data" if os.environ.get("VERCEL") else ROOT / "llm_data"))       # response cache + usage ledger (git-ignored)

PROMPT_VERSION = "cf-v2"
PROVIDER = "cloudflare"
DEFAULT_MODEL = "@cf/google/gemma-4-26b-a4b-it"
MODEL = os.environ.get("CLOUDFLARE_MODEL") or DEFAULT_MODEL
ENABLE_THINKING = os.environ.get("CLOUDFLARE_ENABLE_THINKING", "0") == "1"   # off: the model otherwise spends 5-8x more tokens/neurons on hidden reasoning

BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "8"))            # reviews per extraction request (batch pipeline)
UPLOAD_BATCH_SIZE = int(os.environ.get("UPLOAD_BATCH_SIZE", "6"))   # reviews per request when analysing an uploaded CSV
MAX_REVIEW_CHARS = int(os.environ.get("MAX_REVIEW_CHARS", "1800"))  # prompt-side truncation (quotes are verified against the FULL text)
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", "5"))
REQUEST_TIMEOUT = float(os.environ.get("REQUEST_TIMEOUT", "120"))
CONCURRENCY = int(os.environ.get("CLOUDFLARE_CONCURRENCY", "3"))     # parallel requests while analysing an upload
MAX_ANALYSIS_REVIEWS = int(os.environ.get("MAX_ANALYSIS_REVIEWS", "300"))   # reviews analysed per uploaded file (neuron safety)
DAILY_NEURON_BUDGET = float(os.environ.get("CLOUDFLARE_DAILY_NEURON_BUDGET", "9000"))   # free plan is 10,000 neurons/day (resets 00:00 UTC)
SEED = int(os.environ.get("LLM_SEED", "42"))


def account_id():
    return (os.environ.get("CLOUDFLARE_ACCOUNT_ID") or "").strip() or None


def api_token():
    return (os.environ.get("CLOUDFLARE_API_TOKEN") or "").strip() or None


def is_configured():
    return bool(account_id() and api_token())


def status():
    """Safe, secret-free description of the configuration."""
    return {"provider": PROVIDER, "model": MODEL, "configured": is_configured(), "account_id_set": bool(account_id()), "api_token_set": bool(api_token()),
            "thinking_enabled": ENABLE_THINKING, "daily_neuron_budget": DAILY_NEURON_BUDGET}
