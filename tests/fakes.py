"""A fake Cloudflare Workers AI HTTP transport for offline tests. It answers the prompts used by the backend with deterministic JSON,
mimics real model quirks (fenced JSON, ids echoed as "[ROW-00001]"), and counts calls. No network, no credentials."""
import json
import re

TOKEN = "cfut_TEST_TOKEN_must_never_appear_anywhere"


def ok_body(text, prompt_tokens=100, completion_tokens=50, neurons=2.0, finish="stop"):
    return {"success": True, "errors": [], "messages": [], "result": {"choices": [{"message": {"role": "assistant", "content": text}, "finish_reason": finish}],
                                                                       "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens, "total_tokens": prompt_tokens + completion_tokens, "neurons": neurons}}}


def err_body(code, message):
    return {"success": False, "errors": [{"code": code, "message": message}], "messages": [], "result": None}


def fenced(obj):
    return "```json\n" + json.dumps(obj, ensure_ascii=False, indent=1) + "\n```"


class FakeCloudflare:
    def __init__(self, neurons=2.0):
        self.calls = 0
        self.payloads = []
        self.neurons = neurons
        self.fail_extract_for = set()      # row ids whose extraction the model "forgets"

    def __call__(self, url, headers, payload, timeout):
        self.calls += 1
        self.payloads.append(payload)
        assert headers["Authorization"] == f"Bearer {TOKEN}" or headers["Authorization"].startswith("Bearer "), "token must be sent as a bearer header"
        msgs = payload["messages"]
        system, user = msgs[0]["content"], msgs[-1]["content"]
        for m in msgs:
            if m["role"] == "user":
                user = m["content"]
        body = self.respond(system, msgs[1]["content"] if len(msgs) > 1 else "")
        return 200, {"cf-ai-neurons": str(self.neurons), "cf-ai-req-id": f"req-{self.calls}"}, ok_body(body, neurons=self.neurons)

    # ---------------------------------------------------------------------------------------------- behaviours
    def respond(self, system, user):
        if "extract structured evidence as JSON" in system:
            return fenced(self.extract(user))
        if "grouping short theme labels" in system:
            return fenced(self.themes(user))
        if "You are given computed statistics" in system:
            return fenced(self.insights(user))
        if "You answer ONE question" in system:
            if "capital of France" in user:
                return fenced({"in_scope": False})
            return fenced(self.answer(user))
        if "Rewrite the analysed answer as a crisp brief" in system:
            return fenced({"headline": "Quality drives returns, trust failures deter them", "answer": "Customers return for skilled professionals. Unresolved problems push them away."} if "BAD NUMBER" not in user else {"headline": "x", "answer": "Returns rose 99% overall."})
        return fenced({"ok": True})

    def extract(self, user):
        res = []
        for m in re.finditer(r"\[(ROW-\d{5})\][^\n]*\nTEXT: (.*?)(?=\n\n\[ROW-|\Z)", user, re.S):
            rid, text = m.group(1), " ".join(m.group(2).split())
            if rid in self.fail_extract_for:
                continue
            low = text.lower()
            neg = any(w in low for w in ("late", "cancel", "refused", "damaged", "not available", "no professionals", "ticket", "overcharg", "charged", "chatbot", "never"))
            pos = any(w in low for w in ("great", "lovely", "polite", "skilled", "quickly", "definitely"))
            themes = []
            if "late" in low or "cancel" in low:
                themes.append("late arrival")
            if "support" in low or "chat" in low or "ticket" in low:
                themes.append("customer support")
            if "charged" in low or "price" in low:
                themes.append("high price")
            if pos:
                themes.append("polite professional")
            if not themes:
                themes.append("general service")
            first = re.split(r"(?<=[.!?])\s", text)[0]
            quote = "THIS QUOTE WAS INVENTED BY THE MODEL" if rid.endswith("3") else first[:180]   # one fabricated quote per batch: must be replaced
            res.append({"review_id": f"[{rid}]", "is_customer_experience": True, "sentiment": "Mixed" if (neg and pos) else "Negative" if neg else "Positive" if pos else "Neutral",
                        "themes": themes[:2], "return_signal": "will_return" if "definitely" in low else "warns_others" if "do not use" in low else "none", "problem": "late or poor service" if neg else None, "positive": "polite professional" if pos else None, "key_quote": quote})
        return {"results": res}

    def themes(self, user):
        labels = re.findall(r"^(.+?) \| \d+$", user, re.M)
        a, b = labels[::2], labels[1::2]
        out = [{"name": "Service delivery", "description": "How the service was carried out.", "labels": a}]
        if b:
            out.append({"name": "Support and pricing", "description": "Support and price topics.", "labels": b})
        return {"themes": out}

    def insights(self, user):
        quotes = re.findall(r'QUOTE \[(ROW-\d{5})\] \(\w+\): "(.*?)"$', user, re.M)
        (r1, q1), (r2, q2) = quotes[0], quotes[1]
        return {"insights": [
            {"title": "Delays frustrate customers", "insight": "Customers describe professionals who arrive late and do not communicate.", "supporting": [{"review_id": r1, "quote": q1}, {"review_id": r1, "quote": "A FABRICATED CITATION"}]},
            {"title": "Support gaps", "insight": "Many customers say support did not help.", "supporting": [{"review_id": r2, "quote": q2}]},
            {"title": "Digits are not allowed", "insight": "Exactly 99 percent of customers agree.", "supporting": [{"review_id": r1, "quote": q1}]},
            {"title": "No real evidence", "insight": "A claim that cites nothing real.", "supporting": [{"review_id": r1, "quote": "NOT IN ANY REVIEW"}]}],
            "positive_experiences_summary": "Customers valued polite and skilled professionals.", "negative_experiences_summary": "Customers were let down by delays and weak support.",
            "opportunities": [
                {"name": "Proactive delay alerts", "customer_problem": "Professionals arrive late without warning.", "related_themes": ["Service delivery", "Not a real theme"], "why_it_matters": "Trust in the booking.",
                 "suggested_improvement_hypothesis": "Send live arrival updates.", "repeat_booking_link_hypothesis": "Fewer failed first bookings may raise repeat bookings.", "impact_score_1_to_5": 4, "supporting": [{"review_id": r1, "quote": q1}]},
                {"name": "Ungrounded idea", "customer_problem": "None.", "related_themes": [], "why_it_matters": "-", "suggested_improvement_hypothesis": "-", "repeat_booking_link_hypothesis": "-",
                 "impact_score_1_to_5": 9, "supporting": [{"review_id": r2, "quote": "MADE UP"}]}]}

    def answer(self, user):
        m = re.search(r"\[([A-Z]{2}-\d{4})\][^\n]*\n(.*?)(?=\n\n\[|\Z)", user, re.S)
        rid, text = m.group(1), " ".join(m.group(2).split())
        quote = re.sub(r"^… ", "", text)[:90].rsplit(" ", 1)[0]
        return {"in_scope": True, "headline": "Customers describe it in their own words", "answer": "Customers in the retrieved reviews describe this issue in their own words [" + rid + "].", "evidence_strength": "strong",
                "citations": [{"review_id": rid, "quote": quote}, {"review_id": rid, "quote": "A QUOTE THAT IS NOT IN THE REVIEW"}]}
