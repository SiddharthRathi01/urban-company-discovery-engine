"""Offline tests for the Cloudflare Workers AI client: usage tracking, retries, errors, cache, JSON handling, secrecy of the token."""
import json

import pytest

from backend import config
from backend import llm as L
from tests.fakes import TOKEN, err_body, fenced, ok_body


@pytest.fixture
def mk(tmp_path, monkeypatch):
    monkeypatch.setattr(L.time, "sleep", lambda s: None)
    monkeypatch.setattr(config, "MAX_RETRIES", 3)

    def make(responses):
        seq = list(responses)
        calls = []

        def transport(url, headers, payload, timeout):
            calls.append((url, payload))
            r = seq.pop(0) if len(seq) > 1 else seq[0]
            return r if isinstance(r, tuple) else (200, {"cf-ai-neurons": "1.5"}, r)
        llm = L.CloudflareLLM(cache_dir=tmp_path / "cache", transport=transport, tracker=L.UsageTracker(tmp_path / "usage.jsonl"), account="acc123", token=TOKEN)
        return llm, calls, tmp_path / "usage.jsonl"
    return make


def test_success_records_tokens_neurons_and_disables_thinking(mk):
    llm, calls, ledger = mk([ok_body("hello", prompt_tokens=11, completion_tokens=7, neurons=0.5)])
    r = llm.chat([{"role": "user", "content": "hi"}], purpose="unit")
    assert r["text"] == "hello" and r["usage"]["input_tokens"] == 11 and r["usage"]["output_tokens"] == 7 and r["neurons"] == 0.5
    url, payload = calls[0]
    assert url == "https://api.cloudflare.com/client/v4/accounts/acc123/ai/run/@cf/google/gemma-4-26b-a4b-it"
    assert payload["chat_template_kwargs"] == {"enable_thinking": False}
    s = llm.tracker.summary()
    assert s["requests"] == 1 and s["input_tokens"] == 11 and s["output_tokens"] == 7 and s["neurons"] == 0.5 and s["by_purpose"]["unit"]["requests"] == 1
    assert llm.stats["prompt_tokens"] == 11 and llm.stats["neurons"] == 0.5


def test_neurons_fall_back_to_header(mk):
    body = ok_body("x")
    del body["result"]["usage"]["neurons"]
    llm, _, _ = mk([(200, {"cf-ai-neurons": "3.25"}, body)])
    assert llm.chat([{"role": "user", "content": "hi"}])["neurons"] == 3.25


def test_token_never_leaks_into_ledger_errors_or_cache(mk, tmp_path):
    llm, _, ledger = mk([(401, {}, err_body(10000, f"Authentication error for Bearer {TOKEN}"))])
    with pytest.raises(L.LLMFatal) as e:
        llm.chat([{"role": "user", "content": "hi"}])
    assert TOKEN not in str(e.value)
    for p in tmp_path.rglob("*"):
        if p.is_file():
            assert TOKEN not in p.read_text(encoding="utf-8", errors="ignore"), p
    assert llm.stats["failed_requests"] == 1 and llm.stats["api_calls"] == 1      # fatal errors are not retried


def test_rate_limit_then_success_is_retried(mk):
    llm, calls, _ = mk([(429, {}, err_body(2001, "Rate limited")), ok_body("fine")])
    assert llm.chat([{"role": "user", "content": "hi"}])["text"] == "fine"
    assert len(calls) == 2 and llm.stats["retries"] == 1 and llm.tracker.summary()["failed_requests"] == 1


def test_persistent_server_error_raises_service_unavailable(mk):
    llm, calls, _ = mk([(503, {}, err_body(3040, "Capacity temporarily exceeded"))])
    with pytest.raises(L.ServiceUnavailable):
        llm.chat([{"role": "user", "content": "hi"}])
    assert len(calls) == 3


def test_unknown_model_and_daily_limit_are_fatal(mk):
    llm, _, _ = mk([(404, {}, err_body(5007, "No such model"))])
    with pytest.raises(L.LLMFatal):
        llm.chat([{"role": "user", "content": "hi"}])
    llm, _, _ = mk([(429, {}, err_body(4006, "you have used up your daily free allocation of 10,000 neurons"))])
    with pytest.raises(L.DailyLimitReached):
        llm.chat([{"role": "user", "content": "hi"}])


def test_daily_budget_blocks_requests_before_calling(mk, monkeypatch):
    llm, calls, _ = mk([ok_body("x", neurons=60.0)])
    monkeypatch.setattr(config, "DAILY_NEURON_BUDGET", 50.0)
    llm.chat([{"role": "user", "content": "hi"}])                 # uses 60 neurons
    with pytest.raises(L.DailyLimitReached):
        llm.chat([{"role": "user", "content": "again"}])
    assert len(calls) == 1


def test_call_json_parses_fences_caches_and_retries_invalid_output(mk):
    good = ok_body(fenced({"value": 3}))
    llm, calls, _ = mk([ok_body("not json at all"), good])
    check = lambda o: o if o["value"] == 3 else (_ for _ in ()).throw(ValueError("bad"))
    v, meta = llm.call_json("unit", "sys", "user", check)
    assert v == {"value": 3} and not meta["cached"] and len(calls) == 2 and llm.stats["validation_retries"] == 1
    v2, meta2 = llm.call_json("unit", "sys", "user", check)           # identical request: served from disk, no new call, no new neurons
    assert v2 == {"value": 3} and meta2["cached"] and len(calls) == 2 and llm.stats["cache_hits"] == 1
    assert llm.tracker.summary()["requests"] == 2


def test_truncated_output_raises_incomplete(mk):
    llm, _, _ = mk([ok_body('{"a":', finish="length")])
    with pytest.raises(L.IncompleteResponse):
        llm.call_json("unit", "s", "u", lambda o: o)


def test_missing_credentials_are_reported(monkeypatch):
    monkeypatch.setattr(config, "account_id", lambda: None)
    monkeypatch.setattr(config, "api_token", lambda: None)
    with pytest.raises(L.MissingAPIKey):
        L.CloudflareLLM()
    assert config.is_configured() is False


def test_extract_json_variants():
    assert L.extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert L.extract_json('Here you go: {"a": 1} thanks') == {"a": 1}
    with pytest.raises(ValueError):
        L.extract_json("no json")


def test_check_connection_reports_failure_without_raising(mk):
    llm, _, _ = mk([(401, {}, err_body(10000, "Authentication error"))])
    r = llm.check_connection()
    assert r["connected"] is False and "Cloudflare rejected the credentials" in r["error"]
