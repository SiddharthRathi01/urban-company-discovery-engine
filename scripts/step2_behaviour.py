"""Return / non-return classification of every review (Step 2, revision 2).

Every review is placed in one of three classes:
    Return              the customer is likely to book again
    Non-Return          the customer is unlikely to book again
    Insufficient Evidence   cannot be told either way
and carries HOW that was decided (basis) and how sure we are (confidence):

    basis "Stated"      the reviewer says it in the first person (repeat use / will book again / will not return, switched, uninstalled)  -> High
    basis "Signalled"   the reviewer advises others against using it, mentions switching, expresses distrust, or recommends / praises with trust  -> Medium
    basis "Inferred"    no explicit behaviour: the overall sentiment (and star rating where there is one) points one way
                        Positive -> Return, Negative -> Non-Return; Mixed / Neutral only when the star rating is clear (4-5 or 1-2)
                        confidence Medium when sentiment and rating agree, Low otherwise

A review whose sentiment and rating contradict each other, or that is neutral / mixed without a clear rating, stays Insufficient Evidence.
This is a PREDICTION from public text, not an observed repeat-booking rate."""
import pandas as pd


def classify(legacy_class, legacy_sub, sentiment, rating):
    """Returns (return_class, basis, confidence, reason)."""
    if legacy_class == "Explicit Return":
        return "Return", "Stated", "High", legacy_sub
    if legacy_class == "Explicit Non-Return":
        return "Non-Return", "Stated", "High", legacy_sub
    if legacy_class == "Behavioural Signal":
        if legacy_sub.startswith("warns others"):
            return "Non-Return", "Signalled", "Medium", "advises others not to use the app"
        if legacy_sub.startswith("switching"):
            return "Non-Return", "Signalled", "Medium", "mentions switching to or comparing with alternatives"
        if legacy_sub.startswith("distrust"):
            return "Non-Return", "Signalled", "Medium", "expresses distrust or a safety/honesty concern"
        if legacy_sub.startswith("satisfaction"):
            return "Return", "Signalled", "Medium", "expresses satisfaction, trust or recommends"
    r = None if rating is None or pd.isna(rating) else float(rating)
    if sentiment == "Positive":
        if r is not None and r <= 2:
            return "Insufficient Evidence", "Inferred", "Low", "positive wording but a low star rating"
        return "Return", "Inferred", ("Medium" if r is not None and r >= 4 else "Low"), "positive experience"
    if sentiment == "Negative":
        if r is not None and r >= 4:
            return "Insufficient Evidence", "Inferred", "Low", "negative wording but a high star rating"
        return "Non-Return", "Inferred", ("Medium" if r is not None and r <= 2 else "Low"), "negative experience"
    if r is not None and r >= 4:
        return "Return", "Inferred", "Low", f"{sentiment.lower()} wording with a high star rating"
    if r is not None and r <= 2:
        return "Non-Return", "Inferred", "Low", f"{sentiment.lower()} wording with a low star rating"
    return "Insufficient Evidence", "None", "Low", "no clear positive or negative signal"
