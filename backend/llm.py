"""Cloudflare Workers AI client (REST). The only LLM provider.

* JSON-mode helper with schema validation and a disk cache (identical requests are never paid for twice).
* Retries with back-off for 429 / 5xx / timeouts; clear fatal errors for bad credentials or an unknown model.
* Every request (success or failure) is written to a usage ledger: input/output tokens, neurons, seconds, status. The token is never recorded.
It RAISES on failure; callers log it. It never fabricates or substitutes a result."""
import hashlib
import json
import random
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from . import config


class MissingAPIKey(RuntimeError):
    """Cloudflare credentials are not configured."""


class LLMFatal(RuntimeError):
    """Authentication / model-not-found / other errors that retrying cannot fix."""


class DailyLimitReached(RuntimeError):
    """The daily neuron allowance (or the configured budget) is used up. Stop and resume later; finished work is cached."""


class LLMFailure(RuntimeError):
    """A single request failed after all retries or never produced valid structured output."""


class ServiceUnavailable(LLMFailure):
    """Provider-side capacity problem (HTTP 5xx / timeouts). Splitting the batch will not help."""


class IncompleteResponse(LLMFailure):
    """finish_reason == 'length' (output truncated). Caller should retry with a smaller batch."""


# ------------------------------------------------------------------------------------------------ usage ledger
class UsageTracker:
    """Append-only JSONL ledger of LLM requests plus in-memory totals. Thread-safe."""

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def record(self, **entry):
        entry = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), **entry}
        with self._lock, open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def entries(self):
        if not self.path.exists():
            return []
        with self._lock:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        out = []
        for ln in lines:
            try:
                out.append(json.loads(ln))
            except ValueError:
                continue
        return out

    @staticmethod
    def summarise(entries):
        ok = [e for e in entries if e.get("status") == "ok"]
        failed = [e for e in entries if e.get("status") != "ok"]
        by = {}
        for e in entries:
            p = by.setdefault(e.get("purpose", "other"), {"requests": 0, "failed": 0, "input_tokens": 0, "output_tokens": 0, "neurons": 0.0, "seconds": 0.0})
            p["requests"] += 1
            p["failed"] += e.get("status") != "ok"
            p["input_tokens"] += e.get("input_tokens") or 0
            p["output_tokens"] += e.get("output_tokens") or 0
            p["neurons"] += e.get("neurons") or 0.0
            p["seconds"] += e.get("seconds") or 0.0
        for p in by.values():
            p["neurons"], p["seconds"] = round(p["neurons"], 3), round(p["seconds"], 2)
        return {"requests": len(entries), "successful_requests": len(ok), "failed_requests": len(failed),
                "input_tokens": sum(e.get("input_tokens") or 0 for e in entries), "output_tokens": sum(e.get("output_tokens") or 0 for e in entries),
                "neurons": round(sum(e.get("neurons") or 0.0 for e in entries), 3), "seconds": round(sum(e.get("seconds") or 0.0 for e in entries), 2),
                "by_purpose": by}

    def summary(self, since_ts=None):
        es = self.entries()
        if since_ts:
            es = [e for e in es if e["ts"] >= since_ts]
        return self.summarise(es)

    def today_neurons(self):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return round(sum(e.get("neurons") or 0.0 for e in self.entries() if e["ts"].startswith(today)), 3)


_tracker = None


def get_tracker():
    global _tracker
    if _tracker is None:
        _tracker = UsageTracker(config.LLM_DATA_DIR / "usage.jsonl")
    return _tracker


# ------------------------------------------------------------------------------------------------ helpers
def extract_json(text):
    """Parse a JSON object from model output: tolerates ```json fences and leading/trailing prose."""
    t = (text or "").strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.I)
    try:
        return json.loads(t)
    except ValueError:
        a, z = t.find("{"), t.rfind("}")
        if a >= 0 and z > a:
            return json.loads(t[a:z + 1])
        raise


def _http_transport(url, headers, payload, timeout):
    import requests
    r = requests.post(url, headers=headers, json=payload, timeout=timeout)
    try:
        body = r.json()
    except ValueError:
        body = {"raw": r.text[:300]}
    return r.status_code, dict(r.headers), body


_TOKEN_LIKE = re.compile(r"\bcf[a-z]{1,3}_[A-Za-z0-9_\-]{16,}")


def _backoff(attempt):
    return min(60.0, 2.0 ** attempt + random.random())


class CloudflareLLM:
    def __init__(self, cache_dir=None, model=None, transport=None, tracker=None, account=None, token=None):
        self.account = account or config.account_id()
        self._token = token or config.api_token()
        if transport is None and not (self.account and self._token):
            raise MissingAPIKey("Cloudflare credentials are not set (CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN, environment or .env).")
        self.model = model or config.MODEL
        self.transport = transport or _http_transport
        self.tracker = tracker or get_tracker()
        self.cache_dir = Path(cache_dir or (config.LLM_DATA_DIR / "cache"))
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.stats = {"api_calls": 0, "cache_hits": 0, "retries": 0, "validation_retries": 0, "prompt_tokens": 0, "completion_tokens": 0,
                      "neurons": 0.0, "failed_requests": 0, "seconds": 0.0}

    # ------------------------------------------------------------------ low level
    @property
    def url(self):
        return f"https://api.cloudflare.com/client/v4/accounts/{self.account}/ai/run/{self.model}"

    def _headers(self):
        return {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}

    def _bump(self, **kw):
        with self._lock:
            for k, v in kw.items():
                self.stats[k] += v

    def _clean(self, text):
        """Redact the API token (and anything shaped like one) from provider messages before they are logged, stored or raised."""
        t = str(text or "")
        if self._token:
            t = t.replace(self._token, "[REDACTED]")
        return _TOKEN_LIKE.sub("[REDACTED]", t)

    def _check_budget(self):
        used = self.tracker.today_neurons()
        if used >= config.DAILY_NEURON_BUDGET:
            raise DailyLimitReached(f"Today's neuron budget is used up ({used:.0f} of {config.DAILY_NEURON_BUDGET:.0f}). Raise CLOUDFLARE_DAILY_NEURON_BUDGET or retry after 00:00 UTC.")

    def chat(self, messages, max_tokens=800, temperature=0.0, purpose="chat"):
        """One request with retries. Returns {"text", "finish_reason", "usage": {...}, "neurons", "seconds", "attempts"}."""
        payload = {"messages": messages, "max_tokens": max_tokens, "temperature": temperature}
        if not config.ENABLE_THINKING:
            payload["chat_template_kwargs"] = {"enable_thinking": False}
        last = None
        for attempt in range(1, config.MAX_RETRIES + 1):
            self._check_budget()
            t0 = time.time()
            self._bump(api_calls=1)
            try:
                status, headers, body = self.transport(self.url, self._headers(), payload, config.REQUEST_TIMEOUT)
            except Exception as exc:  # noqa: BLE001  (timeouts, connection errors)
                dt = time.time() - t0
                self.tracker.record(purpose=purpose, model=self.model, status="network_error", error=type(exc).__name__, seconds=round(dt, 2))
                self._bump(failed_requests=1, retries=1, seconds=dt)
                last = ServiceUnavailable(f"network error: {type(exc).__name__}")
                time.sleep(_backoff(attempt))
                continue
            dt = time.time() - t0
            errors = (body or {}).get("errors") or []
            code = errors[0].get("code") if errors else None
            msg = self._clean((errors[0].get("message") if errors else "") or "")
            if status == 200 and (body or {}).get("success", True) and not errors:
                res = body.get("result", body)
                choice = (res.get("choices") or [{}])[0]
                text = (choice.get("message") or {}).get("content") or res.get("response") or ""
                usage = res.get("usage") or {}
                neurons = usage.get("neurons")
                if neurons is None:
                    try:
                        neurons = float(headers.get("cf-ai-neurons") or headers.get("CF-AI-Neurons") or 0)
                    except (TypeError, ValueError):
                        neurons = 0.0
                meta = {"text": text, "finish_reason": choice.get("finish_reason"), "neurons": float(neurons or 0.0), "seconds": round(dt, 2), "attempts": attempt,
                        "usage": {"input_tokens": usage.get("prompt_tokens"), "output_tokens": usage.get("completion_tokens"), "total_tokens": usage.get("total_tokens")}}
                self.tracker.record(purpose=purpose, model=self.model, status="ok", input_tokens=usage.get("prompt_tokens"), output_tokens=usage.get("completion_tokens"),
                                    neurons=meta["neurons"], seconds=meta["seconds"], finish_reason=meta["finish_reason"], request_id=headers.get("cf-ai-req-id"))
                self._bump(prompt_tokens=usage.get("prompt_tokens") or 0, completion_tokens=usage.get("completion_tokens") or 0, neurons=meta["neurons"], seconds=dt)
                return meta
            # ---- failure
            self.tracker.record(purpose=purpose, model=self.model, status=f"http_{status}", error_code=code, error=msg[:160], seconds=round(dt, 2))
            self._bump(failed_requests=1, seconds=dt)
            low = msg.lower()
            if status in (401, 403) or code in (10000, 9109, 1000):
                raise LLMFatal(f"Cloudflare rejected the credentials (HTTP {status}, code {code}): {msg[:120]}")
            if status == 404 or code in (5007, 5018, 7003, 7000) or "no such model" in low:
                raise LLMFatal(f"Model '{self.model}' or the account route was not found (HTTP {status}, code {code}): {msg[:120]}")
            if code == 4006 or "daily free allocation" in low or "neurons" in low and "limit" in low:
                raise DailyLimitReached(msg[:300])
            if status == 429:
                self._bump(retries=1)
                last = LLMFailure(f"rate limited (HTTP 429): {msg[:100]}")
                time.sleep(_backoff(attempt) + 2)
                continue
            if status >= 500 or code in (3040, 3043):
                self._bump(retries=1)
                last = ServiceUnavailable(f"provider error (HTTP {status}, code {code}): {msg[:100]}")
                time.sleep(_backoff(attempt))
                continue
            raise LLMFatal(f"Cloudflare rejected the request (HTTP {status}, code {code}): {msg[:160]}")
        raise last or LLMFailure("request failed after retries")

    # ------------------------------------------------------------------ connectivity
    def check_connection(self):
        t0 = time.time()
        try:
            r = self.chat([{"role": "user", "content": "Reply with the single word: ok"}], max_tokens=16, purpose="connection_check")
        except (LLMFatal, LLMFailure, DailyLimitReached) as e:
            return {"connected": False, "model": self.model, "error": f"{type(e).__name__}: {e}"}
        return {"connected": True, "model": self.model, "test_completion": r["text"].strip()[:30], "usage": r["usage"], "neurons": r["neurons"],
                "latency_s": round(time.time() - t0, 2)}

    # ------------------------------------------------------------------ structured call
    def call_json(self, task, system, user, validate, max_tokens=3500):
        """validate(obj) -> validated object, raising ValueError/pydantic error if invalid. Returns (validated, meta)."""
        key = hashlib.sha256(json.dumps([config.PROMPT_VERSION, self.model, task, system, user], ensure_ascii=False).encode("utf-8")).hexdigest()
        cpath = self.cache_dir / f"{re.sub(r'[^A-Za-z0-9_-]', '_', task)[:40]}__{key[:24]}.json"
        if cpath.exists():
            try:
                cached = json.loads(cpath.read_text(encoding="utf-8"))
                validated = validate(cached["parsed"])
                self._bump(cache_hits=1)
                return validated, {"cached": True, **cached.get("meta", {})}
            except Exception:  # corrupt/outdated cache entry -> recompute
                cpath.unlink(missing_ok=True)

        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        last_err, validation_attempts = None, 0
        for attempt in range(1, 4):
            r = self.chat(messages, max_tokens=max_tokens, purpose=task)
            if r["finish_reason"] == "length":
                raise IncompleteResponse("Response truncated (finish_reason=length); retry with a smaller batch.")
            raw = r["text"]
            try:
                parsed = extract_json(raw)
                validated = validate(parsed)
            except Exception as ve:  # noqa: BLE001  (json or schema validation problem)
                validation_attempts += 1
                self._bump(validation_retries=1)
                last_err = ve
                messages = [{"role": "system", "content": system}, {"role": "user", "content": user}, {"role": "assistant", "content": raw[:6000]},
                            {"role": "user", "content": "Your JSON failed validation: " + str(ve)[:700] +
                             "\nReturn the COMPLETE corrected JSON only. Do not invent facts; use null where the review does not say."}]
                continue
            meta = {"model": self.model, "attempts": r["attempts"], "prompt_version": config.PROMPT_VERSION, "usage": r["usage"], "neurons": r["neurons"], "seconds": r["seconds"]}
            cpath.write_text(json.dumps({"parsed": parsed, "meta": meta}, ensure_ascii=False), encoding="utf-8")
            return validated, {"cached": False, **meta}
        self._bump(failed_requests=1)
        raise LLMFailure(f"{task}: invalid structured output after retries: {type(last_err).__name__}: {str(last_err)[:300]}")
