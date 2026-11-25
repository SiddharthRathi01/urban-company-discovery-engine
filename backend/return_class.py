"""Return / Non-Return classification used by the live engine (uploaded CSVs and the golden-set evaluation).

It applies the SAME rules as the precomputed Urban Company analysis (scripts/step2_behaviour.py; a test keeps the two in step):
    Stated      the reviewer says it in the first person (will book again / will not return)          -> High confidence
    Signalled   advises others against using the app, or recommends with trust                        -> Medium
    Inferred    otherwise the sentiment decides (Positive -> Return, Negative -> Non-Return); Mixed or Neutral only when the
                star rating is clear (4-5 or 1-2); wording that contradicts the rating stays Insufficient Evidence.
The model supplies only `return_signal` (a reading of what the review says); the class itself is decided here, in code."""

CLASSES = ["Return", "Non-Return", "Insufficient Evidence"]
SIGNALS = ["will_return", "will_not_return", "warns_others", "recommends", "none"]


def classify(signal, sentiment, rating):
    """Returns (return_class, basis, confidence, reason). rating may be None, '' or a number."""
    try:
        r = float(rating) if rating not in (None, "") else None
    except (TypeError, ValueError):
        r = None
    if signal == "will_return":
        return "Return", "Stated", "High", "states repeat use or intent to book again"
    if signal == "will_not_return":
        return "Non-Return", "Stated", "High", "states they will not use it again, have switched or stopped"
    if signal == "warns_others":
        return "Non-Return", "Signalled", "Medium", "advises others not to use the app"
    if signal == "recommends" and sentiment != "Negative":
        return "Return", "Signalled", "Medium", "recommends and expresses trust"
    if sentiment == "Positive":
        if r is not None and r <= 2:
            return "Insufficient Evidence", "Inferred", "Low", "positive wording but a low star rating"
        return "Return", "Inferred", ("Medium" if r is not None and r >= 4 else "Low"), "positive experience"
    if sentiment == "Negative":
        if r is not None and r >= 4:
            return "Insufficient Evidence", "Inferred", "Low", "negative wording but a high star rating"
        return "Non-Return", "Inferred", ("Medium" if r is not None and r <= 2 else "Low"), "negative experience"
    if r is not None and r >= 4:
        return "Return", "Inferred", "Low", "mixed or neutral wording with a high star rating"
    if r is not None and r <= 2:
        return "Non-Return", "Inferred", "Low", "mixed or neutral wording with a low star rating"
    return "Insufficient Evidence", "None", "Low", "no clear positive or negative signal"


def summarise(classes, bases):
    n = len(classes)
    c = {k: sum(1 for x in classes if x == k) for k in CLASSES}
    b = {k: sum(1 for x, y in zip(classes, bases) if y == k and x != "Insufficient Evidence") for k in ("Stated", "Signalled", "Inferred")}
    classified = c["Return"] + c["Non-Return"]
    pct = lambda v: round(100 * v / n, 1) if n else 0.0
    return {"reviews": n, "return": c["Return"], "non_return": c["Non-Return"], "insufficient": c["Insufficient Evidence"], "classified": classified, "classified_pct": pct(classified),
            "return_pct": pct(c["Return"]), "non_return_pct": pct(c["Non-Return"]), "insufficient_pct": pct(c["Insufficient Evidence"]), "by_basis": b}
