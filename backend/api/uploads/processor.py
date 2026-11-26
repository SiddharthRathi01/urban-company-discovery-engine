"""Pluggable processing of uploaded reviews.

Processors analyse validated uploads. Registered: "none" (records status 'not_configured', analyses nothing) and "cloudflare"
(Cloudflare Workers AI, see cloudflare_processor.py; the default whenever Cloudflare credentials are set). A processor receives the validated
rows and a private directory under uploads/<upload_id>/ and returns a JobOutcome; it must never write to analysis/ or output/, so uploaded data
cannot change the precomputed Urban Company results. A processor with long_running=True runs in a background thread and receives
process(upload_dir, rows, progress=callback, context=dict).
"""
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol

log = logging.getLogger("discovery.processor")

JOB_STATUSES = ("queued", "running", "completed", "failed", "not_configured")


@dataclass
class JobOutcome:
    status: str
    message: str
    result: dict | None = None            # on 'completed': {"schema_version": "1.0", "files": [...relative names inside the upload folder...], "summary": {...}}
    extra: dict = field(default_factory=dict)


class DiscoveryProcessor(Protocol):
    name: str
    configured: bool

    def process(self, upload_dir: Path, rows: list[dict]) -> JobOutcome: ...


class NotConfiguredProcessor:
    name, configured = "none", False

    def __init__(self, note=None):
        self.note = note

    def process(self, upload_dir, rows):
        msg = ("No analysis provider is configured for uploaded data. The upload is validated and stored; it has not been analysed, "
               "and the precomputed Urban Company analysis is unchanged.")
        return JobOutcome("not_configured", self.note or msg, None, {"rows_received": len(rows)})


_REGISTRY: dict[str, Callable[[], DiscoveryProcessor]] = {"none": NotConfiguredProcessor}


def register_processor(name, factory):
    _REGISTRY[name.lower()] = factory


def get_processor(name):
    from .cloudflare_processor import CloudflareProcessor
    _REGISTRY.setdefault("cloudflare", CloudflareProcessor)
    f = _REGISTRY.get((name or "none").lower())
    if f is None:
        log.warning("unknown UPLOAD_PROCESSOR '%s'; uploads will not be analysed", name)
        return NotConfiguredProcessor(f"Unknown upload processor '{name}'. Registered: {sorted(_REGISTRY)}. The upload has not been analysed.")
    return f()
