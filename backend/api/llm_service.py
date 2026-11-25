"""Shared access to the LLM (Cloudflare Workers AI) for the API. One client per process; tests can inject a fake factory."""
import threading

from backend import config
from backend.llm import CloudflareLLM, get_tracker

_lock = threading.Lock()
_factory = None
_llm = None


def set_llm_factory(factory):
    """Tests: replace the LLM with a fake (factory() -> object with call_json/chat/stats/model). Pass None to restore the real client."""
    global _factory, _llm
    with _lock:
        _factory, _llm = factory, None


def is_configured():
    return _factory is not None or config.is_configured()


def get_llm():
    global _llm
    with _lock:
        if _llm is None:
            _llm = _factory() if _factory else CloudflareLLM()
        return _llm


def status():
    s = config.status()
    if _factory is not None:
        s = {**s, "configured": True, "injected_for_tests": True}
    t = get_tracker()
    s["usage_today_neurons"] = t.today_neurons()
    return s


def usage_summary():
    t = get_tracker()
    total = t.summary()
    total["neurons_today"] = t.today_neurons()
    total["daily_neuron_budget"] = config.DAILY_NEURON_BUDGET
    return total
