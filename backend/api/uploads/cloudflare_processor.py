"""Upload processor backed by Cloudflare Workers AI. Runs as a background job (long_running) and reports progress."""
import logging

from backend import csv_analysis
from backend.llm import DailyLimitReached, LLMFailure, LLMFatal

from .. import llm_service
from .processor import JobOutcome

log = logging.getLogger("discovery.cloudflare_processor")


class CloudflareProcessor:
    name = "cloudflare"
    long_running = True
    reuses_saved_results = True

    @property
    def configured(self):
        return llm_service.is_configured()

    def process(self, upload_dir, rows, progress=None, context=None):
        if not self.configured:
            return JobOutcome("not_configured", "Cloudflare Workers AI credentials are not set (CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN). The upload is stored but not analysed.", None, {"rows_received": len(rows)})
        context = context or {}
        try:
            result = csv_analysis.analyse(llm_service.get_llm(), rows, upload_dir / "analysis", context.get("upload_id", upload_dir.name), source_filename=context.get("filename"),
                                          rows_in_file=context.get("rows_in_file"), progress=progress)
        except DailyLimitReached as e:
            return JobOutcome("failed", f"Cloudflare daily neuron allowance reached. Finished batches are cached, so re-running later resumes cheaply. {str(e)[:160]}")
        except LLMFatal as e:
            return JobOutcome("failed", f"Cloudflare Workers AI error: {str(e)[:220]}")
        except LLMFailure as e:
            return JobOutcome("failed", f"Analysis could not be completed: {str(e)[:220]}")
        d = result["dataset"]
        msg = f"Analysed {d['reviews_analysed']} reviews into {len(result['themes'])} themes, {len(result['insights'])} insights and {len(result['opportunities'])} opportunities."
        if d["rows_not_analysed_due_to_limit"]:
            msg += f" {d['rows_not_analysed_due_to_limit']} rows beyond the {d['analysis_row_limit']}-review limit were not analysed."
        return JobOutcome("completed", msg, {"schema_version": "1.0", "files": ["analysis/analysis.json", "analysis/reviews.json"],
                                             "summary": {"reviews_analysed": d["reviews_analysed"], "themes": len(result["themes"]), "insights": len(result["insights"]), "opportunities": len(result["opportunities"])},
                                             "usage": result["usage"]})
