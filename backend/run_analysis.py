"""CLI for the Step 2 Discovery Engine backend.

  python -m backend.run_analysis check                         # verify the Cloudflare Workers AI connection + model (no analysis)
  python -m backend.run_analysis run --limit 40 --outdir analysis_pilot   # small pilot run
  python -m backend.run_analysis run                           # full run, resumable (re-run the same command to continue)
  python -m backend.run_analysis status [--outdir analysis]

Cloudflare Workers AI is the only provider. Credentials (CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN) come from the environment or the git-ignored .env
file. The token is never printed or saved. Usage (tokens, neurons) is recorded in llm_data/usage.jsonl."""
import argparse
import json
import sys
from pathlib import Path

from . import config, data, pipeline as P
from .llm import DailyLimitReached, LLMFatal, MissingAPIKey
from .factory import make_llm

STAGES = ["extract", "themes", "unmet", "behaviour", "alternatives", "segments", "questions", "opportunities", "bundle"]


def _outdir(arg):
    p = Path(arg) if arg else config.ANALYSIS_DIR
    return p if p.is_absolute() else config.ROOT / p


def cmd_check(args):
    try:
        llm = make_llm(_outdir(args.outdir) / "cache")
    except MissingAPIKey as e:
        print("LLM API: NOT CONNECTED - " + str(e)); return 2
    r = llm.check_connection()
    print(json.dumps(r, indent=1))
    return 0 if r.get("connected") else 1


def cmd_run(args):
    out = _outdir(args.outdir); out.mkdir(parents=True, exist_ok=True)
    try:
        llm = make_llm(out / "cache")
    except MissingAPIKey as e:
        print("Cannot run: " + str(e) + "\nNothing was processed. No results were generated or simulated."); return 2
    chk = llm.check_connection()
    if not chk.get("connected"):
        print("Cannot run: Cloudflare connection/model check failed:", json.dumps(chk)[:400]); return 1
    df, full = data.load_reviews(include_insta_help=args.include_insta_help)
    if args.limit:
        pass
    stages = args.stages.split(",") if args.stages else STAGES
    P.update_manifest(out, project="Urban Company Discovery Engine - Step 2", model=llm.model, prompt_version=config.PROMPT_VERSION, provider="cloudflare_workers_ai",
                      dataset_file=str(config.MASTER_CSV.relative_to(config.ROOT)), dataset_sha256=data.dataset_sha256(), master_reviews=len(full),
                      analysis_base_reviews=len(df), insta_help_excluded_from_analysis=int(full.insta_help.sum()), run_limit=args.limit or None,
                      temperature=0, seed=config.SEED, batch_size=config.BATCH_SIZE, api_connection=chk)
    sub = df.head(args.limit) if args.limit else df
    try:
        for s in stages:
            print(f"== stage: {s}")
            if s == "extract": P.run_extraction(llm, df, out, limit=args.limit)
            elif s == "themes": P.run_themes(llm, sub, out)
            elif s == "unmet": P.run_unmet_needs(llm, sub, out)
            elif s == "behaviour": P.run_behaviour(sub, out)
            elif s == "alternatives": P.run_alternatives(llm, sub, out)
            elif s == "segments": P.run_segments(sub, out)
            elif s == "questions": P.run_questions(llm, sub, out)
            elif s == "opportunities": P.run_opportunities(llm, sub, out)
            elif s == "bundle": P.build_bundle(sub, full, out)
    except DailyLimitReached as e:
        print("\nCloudflare daily neuron allowance reached. All finished work is saved. Re-run the same command later to resume.\n" + str(e)[:200]); return 3
    except LLMFatal as e:
        print("\nFatal LLM error: " + str(e)); return 1
    finally:
        P.update_manifest(out, llm_stats=llm.stats)
    print("\nDone. LLM stats:", llm.stats)
    return 0


def cmd_status(args):
    out = _outdir(args.outdir)
    m = P.jload(out / "run_manifest.json")
    print("LLM provider:", config.PROVIDER, "| model:", config.MODEL, "| credentials configured:", config.is_configured())
    if not m:
        print("No analysis has been run yet (no manifest in %s)." % out); return 0
    print(json.dumps({k: v for k, v in m.items() if k.startswith("stage_") or k in ("model", "analysis_base_reviews", "run_limit", "llm_stats", "updated_at")}, indent=1))
    print("files:", sorted(p.name for p in out.glob("*.json*")))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="backend.run_analysis")
    sp = ap.add_subparsers(dest="cmd", required=True)
    for name in ("check", "run", "status"):
        s = sp.add_parser(name); s.add_argument("--outdir", default=None)
    r = sp.choices["run"]
    r.add_argument("--limit", type=int, default=None, help="process only the first N reviews (pilot run)")
    r.add_argument("--stages", default=None, help="comma list: " + ",".join(STAGES))
    r.add_argument("--include-insta-help", action="store_true")
    a = ap.parse_args(argv)
    return {"check": cmd_check, "run": cmd_run, "status": cmd_status}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
