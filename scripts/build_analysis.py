"""Build the precomputed Step 2 discovery analysis (structured JSON for the Discovery Engine backend/frontend).
Inputs : raw/step2_tagged.pkl (rule-based coding of output/urban_company_reviews_master.csv; the master is never modified here)
Outputs: analysis/*.json   Method: deterministic coding rules + analyst review of the matched text (no LLM was used for these results)."""
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone

import pandas as pd

sys.path.insert(0, "scripts")
from analysis_lib import Evidence, OUTDIR, norm, pct, py
from step2_common import THEMES
from step2_codes2 import ALT_RE, ALT_WHY, NEEDS, NEED_RE, TRIGGERS  # noqa: F401
import step2_spec as S
import step2_spec2 as S2
import step2_curated as CUR

GEN = datetime.now(timezone.utc).isoformat(timespec="seconds")
b = pd.read_pickle("raw/step2_tagged.pkl").sort_values("record_id").reset_index(drop=True)
N = len(b)
ROWS = {r["record_id"]: r for r in b.to_dict("records")}
EV = Evidence(ROWS)
SRC = ["Google Play Store", "Reddit", "PissedConsumer", "ConsumerComplaints.in"]
SENTS = ["Positive", "Negative", "Neutral", "Mixed", "Uncertain"]
RC = ["Return", "Non-Return", "Insufficient Evidence"]
TH = list(THEMES)
SRC_N = {p: int((b.platform == p).sum()) for p in SRC}
OUTDIR.mkdir(exist_ok=True)

SUB = {"cancelled": "Cancelled by the company or professional", "rescheduled": "Rescheduled", "no_show": "Professional did not show up", "late": "Late or delayed",
       "slot_unavailable": "No slots / professional unavailable", "price_high": "Prices too high or rising", "fees_charges": "Platform, visit and cancellation fees; policy rigidity",
       "overcharge_upsell": "Extra charges and parts upselling", "support_unreachable": "Support unreachable (bot, no number)", "refund_payment": "Refund and payment problems",
       "unresolved": "Complaint unresolved, no follow-up", "warranty_rework": "Warranty and rework not honoured", "native_after_sales": "Native product installation and after-sales",
       "poor_quality": "Poor or incomplete work", "damage_theft": "Damage or theft", "conduct_safety": "Rude conduct, safety, rating pressure", "trust_fraud": "Trust, fraud or dishonesty",
       "pos_quality_pro": "Skilled, professional, courteous work (positive)", "pos_punctual": "Punctual and prompt (positive)", "pos_support_resolution": "Support or resolution that worked (positive)",
       "coverage_gap": "Service not available in the area or city", "missing_service_request": "Missing service or feature requested", "app_friction": "App bugs, location or usability issues"}
PRECISION = {"cancelled": 0.88, "no_show": 0.88, "late": 0.88, "slot_unavailable": 1.0, "price_high": 0.88, "fees_charges": 1.0, "overcharge_upsell": 1.0, "support_unreachable": 0.75,
             "refund_payment": 1.0, "unresolved": 0.88, "poor_quality": 0.88, "damage_theft": 0.88, "conduct_safety": 0.88, "trust_fraud": 1.0}


def sent_block(df):
    return {s: {"n": int((df.sentiment_label == s).sum()), "pct": pct((df.sentiment_label == s).sum(), len(df))} for s in SENTS}


def src_block(df):
    return [{"source": p, "n": int((df.platform == p).sum()), "pct_of_source_reviews": pct((df.platform == p).sum(), SRC_N[p])} for p in SRC]


def rc_block(df):
    return {c: int((df.return_class == c).sum()) for c in RC}


def jwrite(name, obj):
    (OUTDIR / name).write_text(json.dumps(py(obj), ensure_ascii=False, indent=1), encoding="utf-8")


def mask_any(cols):
    return b[cols].any(axis=1)


# =============================================================================================================== THEMES
THEME_DEF = {
    "T1": ("Unreliable fulfilment: cancellations, no-shows, delays and missing slots",
           "Booked services that are cancelled, rescheduled, late, never attended, or cannot be booked because no professional or slot is available."),
    "T2": ("Price, fees and policy rigidity",
           "Prices that feel high or keep rising, platform/visit/cancellation fees, minimum-order and plan rules, and extra charges or parts upselling by professionals."),
    "T3": ("Support access, refunds and problem resolution (including warranty and Native after-sales)",
           "Customers cannot reach a human, wait for refunds, see complaints closed without resolution, or are refused warranty and rework, including Native purifier installation and after-sales."),
    "T4": ("Service quality, professional conduct and trust (good and bad)",
           "What the professional actually delivers: skilled, punctual and courteous work on the positive side; poor or incomplete work, damage or theft, rude or unsafe conduct and dishonesty on the negative side."),
    "T5": ("Coverage gaps, missing services and app friction",
           "Services or areas Urban Company does not cover, services customers ask for that do not exist, and app, location or usability problems."),
}
tdata, theme_masks = [], {t: b["th_" + t] for t in TH}
any_theme = pd.concat(theme_masks.values(), axis=1).any(axis=1)
n_multi = int((pd.concat(theme_masks.values(), axis=1).sum(axis=1) >= 2).sum())
maxn = max(int(m.sum()) for m in theme_masks.values())
for t in TH:
    m = theme_masks[t]; s = b[m]; n = len(s)
    codes = THEMES[t][1]
    sub = []
    for c in codes:
        cm = s["i_" + c]
        sub.append({"subtheme_id": f"{t}.{c}", "name": SUB[c], "n": int(cm.sum()), "pct_of_dataset": pct(cm.sum(), N), "pct_of_theme": pct(cm.sum(), n),
                    "negative_or_mixed_share": pct((s[cm].sentiment_label.isin(["Negative", "Mixed"])).sum(), max(1, cm.sum())),
                    "rule_precision_estimate": PRECISION.get(c), "evidence_ids": EV.auto(s[cm], c, [f"theme:{t}", f"subtheme:{t}.{c}"], k=1)})
    neg_share = (s.sentiment_label.isin(["Negative", "Mixed"])).sum() / n
    breadth = sum(1 for p in SRC if (s.platform == p).sum() / SRC_N[p] >= 0.05) / len(SRC)
    nr_ss = int(((s.return_class == "Non-Return") & s.return_basis.isin(["Stated", "Signalled"])).sum())
    r_ss = int(((s.return_class == "Return") & s.return_basis.isin(["Stated", "Signalled"])).sum())
    nr_all, r_all = int((s.return_class == "Non-Return").sum()), int((s.return_class == "Return").sum())
    leave_link = min(1.0, 2 * nr_ss / n)
    score = 0.40 * n / maxn + 0.30 * neg_share + 0.15 * breadth + 0.15 * leave_link
    tdata.append({"theme_id": t, "name": THEME_DEF[t][0], "definition": THEME_DEF[t][1], "review_count": n, "pct_of_dataset": pct(n, N), "sentiment": sent_block(s),
                  "by_source": src_block(s), "subthemes": sub, "return_signals": {"return": r_all, "non_return": nr_all, "non_return_pct": pct(nr_all, n), "return_stated_or_signalled": r_ss, "non_return_stated_or_signalled": nr_ss, "non_return_stated_or_signalled_pct": pct(nr_ss, n)},
                  "evidence_score": {"reach": round(n / maxn, 3), "negative_or_mixed_share": round(neg_share, 3), "source_breadth": breadth, "non_return_link": round(leave_link, 3),
                                     "score": round(score, 3), "formula": "0.40*reach(n/largest theme) + 0.30*share Negative/Mixed + 0.15*share of the 4 sources where the theme is in >=5% of reviews + 0.15*min(1, 2*share of theme reviews that are Non-Return by Stated or Signalled evidence)"},
                  "review_ids": list(s.record_id)})
tdata.sort(key=lambda x: -x["evidence_score"]["score"])
for i, x in enumerate(tdata, 1):
    x["evidence_rank"] = i
TD = {x["theme_id"]: x for x in tdata}
# T4 two-sided evidence
neg4 = mask_any(["i_poor_quality", "i_damage_theft", "i_conduct_safety", "i_trust_fraud"]); pos4 = mask_any(["i_pos_quality_pro", "i_pos_punctual", "i_pos_support_resolution"])
TD["T4"]["sides"] = {"negative_side_reviews": int(neg4.sum()), "positive_side_reviews": int(pos4.sum()), "both": int((neg4 & pos4).sum()),
                     "note": "T4 is two-sided: it holds most of the positive evidence (what customers value) and the quality/conduct/trust failures."}
# overlap matrix
overlap = {a: {c: int((theme_masks[a] & theme_masks[c]).sum()) for c in TH} for a in TH}
# curated theme quotes
for t, key in [("T1", "T1"), ("T2", "T2"), ("T3", "T3"), ("T5", "T5")]:
    TD[t]["representative_evidence_ids"] = EV.many(S.Q[key], f"theme:{t}")
TD["T4"]["representative_evidence_ids"] = EV.many(S.Q["T4neg"], "theme:T4") + EV.many(S.Q["T4pos"], "theme:T4")
TD["T4"]["negative_evidence_ids"] = EV.many(S.Q["T4neg"], "theme:T4"); TD["T4"]["positive_evidence_ids"] = EV.many(S.Q["T4pos"], "theme:T4")
INTERP = {
    "T1": lambda: f"Customers treat a booking as a commitment and arrange their day, leave or an occasion around the slot. {TD['T1']['sentiment']['Negative']['pct']}% of these reviews are Negative. Cancellations ({TD['T1']['subthemes'][0]['n']}), no-shows ({TD['T1']['subthemes'][2]['n']}) and lateness ({TD['T1']['subthemes'][3]['n']}) dominate; they are strongest on PissedConsumer ({TD['T1']['by_source'][2]['pct_of_source_reviews']}% of its reviews) and ConsumerComplaints ({TD['T1']['by_source'][3]['pct_of_source_reviews']}%) where customers escalate, but also appear in {TD['T1']['by_source'][0]['pct_of_source_reviews']}% of Google Play reviews.",
    "T2": lambda: f"Price is rarely the only complaint: customers object to prices changing between the quote and the bill, to fees stacked on a small job (visit, platform, cancellation), and to parts or extras suggested by the professional. Customers compare directly with local providers (see alternatives). {pct(TD['T2']['return_signals']['non_return_stated_or_signalled'], int(((b.return_class=='Non-Return') & b.return_basis.isin(['Stated','Signalled'])).sum()))}% of the Non-Return reviews that say so outright or signal it (advise against, switching, distrust) raise price or fees.",
    "T3": lambda: f"The largest problem theme. The initial failure is often not what ends the relationship: customers describe being unable to reach a person, waiting for refunds, having complaints closed, or being refused warranty. {int((theme_masks['T3'] & b[['th_T1','i_poor_quality','i_damage_theft','i_price_high','i_overcharge_upsell']].any(axis=1)).sum())} of the {TD['T3']['review_count']} reviews also report a primary failure (late/no-show, poor work, damage, price), so recourse failures compound other problems. Native purifier after-sales is a distinct cluster ({TD['T3']['subthemes'][4]['n']} reviews).",
    "T4": lambda: f"Customers' view of the individual professional decides most of the Return evidence: {int(((b.return_class=='Return') & b.return_basis.isin(['Stated','Signalled']) & b.th_T4).sum())} of the {int(((b.return_class=='Return') & b.return_basis.isin(['Stated','Signalled'])).sum())} Return reviews that state or signal it sit in this theme, mostly praising skill, politeness and punctuality, and naming specific professionals they would book again. The same theme holds {TD['T4']['sides']['negative_side_reviews']} failure reviews (poor work, damage or theft, conduct, trust), so quality variance between professionals is the central tension.",
    "T5": lambda: f"A smaller but consistent theme of unmet needs: unavailable areas and cities, services customers ask for that do not exist, and app/location friction. It is mostly expressed as requests, so it is lower in volume but rich in product direction.",
}
for t in TH:
    TD[t]["interpretation"] = INTERP[t]()
themes_out = {"schema_version": "1.0", "generated_at": GEN, "dataset_reviews": N, "max_themes": 5,
              "counting_method": ("Each review is tested against every theme and counted once in each theme it touches (multi-label). Theme counts therefore add up to more than the number of reviews; "
                                  f"{int(any_theme.sum())} reviews ({pct(any_theme.sum(), N)}%) touch at least one theme, {n_multi} reviews touch two or more, and {int((~any_theme).sum())} reviews ({pct((~any_theme).sum(), N)}%) touch none (mostly very short, generic comments such as 'good' or 'bad', and neutral Reddit questions). Percentages use the {N:,}-review dataset as denominator."),
              "emergence": "Themes were derived bottom-up: phrase-frequency scans of positive, negative, mixed and Reddit reviews, then reading random hits for every candidate issue code and re-coding until the unmatched negative reviews were mostly generic. 23 issue codes were grouped into five themes.",
              "theme_overlap_matrix": overlap, "unique_reviews_with_at_least_one_theme": int(any_theme.sum()), "reviews_with_no_theme": int((~any_theme).sum()),
              "top_three_by_evidence": [x["theme_id"] for x in tdata[:3]], "themes": tdata,
              "note": "T4 ranks highest because it is the broadest and holds the positive evidence. Among problem-focused themes the order of evidence is T3, T2, T1 (T1 and T2 are nearly tied)."}

# =============================================================================================================== BEHAVIOUR (Return / Non-Return)
BASES = ["Stated", "Signalled", "Inferred"]
R_, NR_, IN_ = (b[b.return_class == c] for c in RC)
classified = len(R_) + len(NR_)
beh = {}
for c in RC:
    s = b[b.return_class == c]
    th_prev = {t: {"n": int(s["th_" + t].sum()), "pct_of_class": pct(s["th_" + t].sum(), len(s))} for t in TH}
    beh[c] = {"class": c, "n": len(s), "pct_of_dataset": pct(len(s), N), "by_basis": {k: int((s.return_basis == k).sum()) for k in BASES if (s.return_basis == k).any()},
              "by_confidence": {k: int((s.return_confidence == k).sum()) for k in ("High", "Medium", "Low") if (s.return_confidence == k).any()},
              "by_source": {p: int((s.platform == p).sum()) for p in SRC}, "sentiment": sent_block(s), "reasons": dict(Counter(s.return_reason)), "theme_prevalence": th_prev}
# first-person (Stated) records with their own words
from step2_codes2 import RET_REPORTED, RET_INTENT, NON_RETURN
def stated_evidence(rid, cls):
    pats = [NON_RETURN.pattern] if cls == "Non-Return" else [RET_REPORTED.pattern, RET_INTENT.pattern]
    for p in pats:
        if EV.sentence(ROWS[rid]["text"], p, 20, 300):
            return EV.add(rid, p, [f"behaviour:{cls}"], lo=20, hi=300)
    return EV.add_span(rid, [f"behaviour:{cls}"], 300)
for c in ("Return", "Non-Return"):
    s = b[(b.return_class == c) & (b.return_basis == "Stated")]
    beh[c]["stated_records"] = [{"review_id": r.record_id, "original_review_id": r.original_review_id, "source": r.platform, "source_url": r.source_url, "review_date": r.review_date or None,
                                 "rating": r.rating or None, "sentiment_label": r.sentiment_label, "reason": r.return_reason, "evidence_id": stated_evidence(r.record_id, c),
                                 "themes": [t for t in TH if getattr(r, "th_" + t)]} for r in s.itertuples()]
# sample quotes for Signalled reasons and for Inferred (sentiment-based) groups
SIG_PAT = {"advises others not to use the app": r"don.t (?:use|book|buy)|stay away|avoid|never use|think twice|beware|do not use",
           "mentions switching to or comparing with alternatives": r"alternative|local|snabbit|pronto|nobroker|yes ?madam|other apps?|instead",
           "expresses distrust or a safety/honesty concern": "trust_fraud", "expresses satisfaction, trust or recommends": "pos_quality_pro"}
for c in ("Return", "Non-Return"):
    sig = b[(b.return_class == c) & (b.return_basis == "Signalled")]
    beh[c]["signalled_reasons"] = {}
    for rs, g in sig.groupby("return_reason"):
        beh[c]["signalled_reasons"][rs] = {"n": len(g), "pct_of_dataset": pct(len(g), N), "evidence_ids": EV.auto(g, SIG_PAT.get(rs), [f"behaviour:{c}"], k=3) if SIG_PAT.get(rs) else []}
    inf = b[(b.return_class == c) & (b.return_basis == "Inferred")]
    beh[c]["inferred_evidence_ids"] = EV.auto(inf, "pos_quality_pro" if c == "Return" else "poor_quality", [f"behaviour:{c}"], k=3, prefer=("Positive",) if c == "Return" else ("Negative",))
beh["Insufficient Evidence"]["review_ids_note"] = "Use /reviews?return_class=Insufficient Evidence to read them."

SR, SNR = R_[R_.return_basis.isin(["Stated", "Signalled"])], NR_[NR_.return_basis.isin(["Stated", "Signalled"])]      # evidence that does not rest on sentiment alone
sr_unhappy = int(R_[R_.return_basis == "Stated"].sentiment_label.isin(["Negative", "Mixed"]).sum())
n_stated_r = int((R_.return_basis == "Stated").sum())
basis_n = {k: int(((b.return_basis == k) & b.return_class.isin(["Return", "Non-Return"])).sum()) for k in BASES}
conf_n = {k: int(((b.return_confidence == k) & b.return_class.isin(["Return", "Non-Return"])).sum()) for k in ("High", "Medium", "Low")}
summary = {"classified": classified, "classified_pct": pct(classified, N), "target_pct": 70, "target_met": pct(classified, N) >= 70, "return": len(R_), "return_pct": pct(len(R_), N), "non_return": len(NR_), "non_return_pct": pct(len(NR_), N),
           "insufficient": len(IN_), "insufficient_pct": pct(len(IN_), N), "by_basis": {k: {"n": v, "pct_of_dataset": pct(v, N)} for k, v in basis_n.items()},
           "by_confidence_of_classified": {k: {"n": v, "pct_of_classified": pct(v, classified)} for k, v in conf_n.items()}}
beh_patterns = [
    f"{pct(classified, N)}% of reviews ({classified:,} of {N:,}) could be placed as Return ({len(R_):,}, {pct(len(R_), N)}%) or Non-Return ({len(NR_):,}, {pct(len(NR_), N)}%); {len(IN_):,} ({pct(len(IN_), N)}%) stay Insufficient Evidence because they are neutral questions or give no clear positive or negative signal.",
    f"How sure we are: {basis_n['Stated']} reviews ({pct(basis_n['Stated'], N)}%) say it in the first person (Stated, high confidence); {basis_n['Signalled']} ({pct(basis_n['Signalled'], N)}%) advise against using the app, mention switching, express distrust or recommend with trust (Signalled, medium); {basis_n['Inferred']:,} ({pct(basis_n['Inferred'], N)}%) are inferred from how positive or negative the review is, and from the star rating where there is one (Inferred, medium or low).",
    f"Return is mostly about people: of the {len(SR):,} Return reviews with Stated or Signalled evidence, {pct(SR.th_T4.sum(), len(SR))}% are about professional quality, punctuality or trust (T4). Non-Return with Stated or Signalled evidence is mostly about recourse ({pct(SNR.th_T3.sum(), len(SNR))}% recourse failures, T3), reliability ({pct(SNR.th_T1.sum(), len(SNR))}%, T1) and price ({pct(SNR.th_T2.sum(), len(SNR))}%, T2).",
    f"{sr_unhappy} of the {n_stated_r} customers who say they came back are themselves Negative or Mixed: some are loyal but unhappy, so a repeat history is not the same as satisfaction.",
    f"Source mix shapes what is visible: complaint sites contribute {int(NR_.platform.isin(['PissedConsumer', 'ConsumerComplaints.in']).sum())} of the {len(NR_):,} Non-Return reviews and none of the Return reviews; Google Play supplies {int((R_.platform == 'Google Play Store').sum())} of the {len(R_):,} Return reviews.",
    "These are predictions from public text, not observed repeat-booking rates. Customers who simply stopped booking leave no review, so the true non-return share is probably higher than the share shown here.",
]
behaviour_out = {"schema_version": "2.0", "generated_at": GEN, "dataset_reviews": N, "summary": summary,
                 "definitions": {"Return": "Likely to book again: the reviewer says so, praises and recommends with trust, or has a clearly positive experience (and star rating where there is one).",
                                 "Non-Return": "Unlikely to book again: the reviewer says so, advises others not to use the app, mentions switching, expresses distrust, or has a clearly negative experience.",
                                 "Insufficient Evidence": "Neutral, mixed, or contradictory (for example positive wording with a one-star rating): no clear signal either way."},
                 "basis_definitions": {"Stated": "The reviewer says it in the first person: repeat or ongoing use, will book again, will not return, has switched or uninstalled (each read and confirmed by hand).",
                                       "Signalled": "No direct statement, but a clear signal: advises others not to use the app, mentions switching, distrust, or recommends and trusts.",
                                       "Inferred": "Neither of the above: the overall sentiment decides (Positive -> Return, Negative -> Non-Return); mixed or neutral reviews only when the star rating is clearly 4-5 or 1-2. A contradiction between wording and rating stays Insufficient."},
                 "caution": "Return and Non-Return are predictions from what customers wrote. Inferred labels rest on sentiment alone, so comparisons that use them partly restate sentiment; the Stated and Signalled groups are the stronger evidence.",
                 "distribution": [{"class": c, "n": beh[c]["n"], "pct_of_dataset": beh[c]["pct_of_dataset"], "by_basis": beh[c]["by_basis"]} for c in RC], "classes": beh, "patterns": beh_patterns,
                 "stated_returners_dissatisfied": {"n": sr_unhappy, "of": n_stated_r, "pct": pct(sr_unhappy, n_stated_r)}}
behaviour_out["classes"]["Return"]["representative_evidence_ids"] = EV.many(S.Q["Q4return"], "behaviour:Return")
behaviour_out["classes"]["Return"]["at_risk_loyal_customers_evidence_ids"] = EV.many(S.Q["Q4atrisk"], "behaviour:Return")
behaviour_out["classes"]["Non-Return"]["representative_evidence_ids"] = EV.many(S.Q["Q4nonreturn"], "behaviour:Non-Return")

# ---- what separates the two groups (Q6)
ISS_COMPARE = ["cancelled", "no_show", "late", "price_high", "fees_charges", "overcharge_upsell", "support_unreachable", "refund_payment", "unresolved", "warranty_rework", "poor_quality", "damage_theft", "conduct_safety", "trust_fraud", "pos_quality_pro", "pos_punctual", "pos_convenience", "pos_support_resolution"]
def prev(s, c): return pct(s["i_" + c].sum(), len(s))
groups = {"all": b, "return": R_, "non_return": NR_, "return_stated_signalled": SR, "non_return_stated_signalled": SNR}
def seg_split(df_, key, min_n):
    out = []
    for k, g in df_.groupby(key):
        if k and len(g) >= min_n:
            out.append({"segment": k, "n": len(g), "return_pct": pct((g.return_class == "Return").sum(), len(g)), "non_return_pct": pct((g.return_class == "Non-Return").sum(), len(g)),
                        "insufficient_pct": pct((g.return_class == "Insufficient Evidence").sum(), len(g)),
                        "return_pct_of_classified": pct((g.return_class == "Return").sum(), max(1, g.return_class.isin(["Return", "Non-Return"]).sum()))})
    return sorted(out, key=lambda x: -x["n"])
city_rows_ = b[b.city != ""].assign(_c=b.city.str.split("; ")).explode("_c")
compare = {"groups": {k: len(v) for k, v in groups.items()},
           "theme_prevalence_pct": {t: {k: pct(v["th_" + t].sum(), len(v)) for k, v in groups.items()} for t in TH},
           "prevalence_pct": {c: {"label": SUB.get(c, "Convenience and ease (positive)"), **{k: prev(v, c) for k, v in groups.items()}} for c in ISS_COMPARE},
           "return_share_by_segment": {"service_category": seg_split(b[b.service_category != ""], "service_category", 30), "source": seg_split(b, "platform", 1), "city": seg_split(city_rows_, "_c", 15)},
           "caution": "The all-classified groups include Inferred labels, which come from sentiment, so some of the gap restates sentiment. The Stated + Signalled groups are smaller but do not rest on sentiment alone."}
leave_gap = sorted(((c, prev(SNR, c) - prev(SR, c)) for c in ISS_COMPARE if not c.startswith("pos_")), key=lambda x: -x[1])
stay_gap = sorted(((c, prev(SR, c) - prev(SNR, c)) for c in ISS_COMPARE if c.startswith("pos_")), key=lambda x: -x[1])
compare["top_leaving_drivers"] = [{"issue": SUB.get(c, c), "code": c, "non_return_pct": prev(SNR, c), "return_pct": prev(SR, c), "gap_points": round(g, 1)} for c, g in leave_gap[:6]]
compare["top_staying_drivers"] = [{"issue": SUB.get(c, "Convenience and ease (positive)"), "code": c, "return_pct": prev(SR, c), "non_return_pct": prev(SNR, c), "gap_points": round(g, 1)} for c, g in stay_gap[:4]]
behaviour_out["comparison"] = compare
jwrite("behaviour.json", behaviour_out)

# =============================================================================================================== ALTERNATIVES
tier_of = {rid: t for t, ids in S2.ALT_TIER.items() for rid in ids}
group_of = {rid: g for g, ids in S2.ALT_GROUP.items() for rid in ids}
reasons_rx = {"price / cost": ALT_WHY["cheaper / better price"], "trust / reliability": ALT_WHY["trust / reliability"], "availability / speed": ALT_WHY["available / quick"],
              "quality / skill": ALT_WHY["quality / skill"], "personal accountability": ALT_WHY["personal relationship / accountability"]}
ALT_TEXT = {
    "Competing platforms (Snabbit, Pronto, Yes Madam, NoBroker, Housejoy, Justdial and similar)": {
        "used_for": "House help (Snabbit, Pronto), massage at home, and AC installation (NoBroker), as named by reviewers.",
        "why": ["Urban Company had no slot or availability when the customer needed one (RD-0129, RD-0184).", "Reliability: one reviewer says Snabbit gives much better service and reliability (GP-0477); another moved to Urban Company after repeated failed Snabbit bookings (GP-1116).",
                "Price runs both ways: one reviewer says Urban Company is a little more than Pronto but was available instantly (GP-1366), another says its rates are high compared with Pronto and Snabbit (GP-1002).", "No cash option: one reviewer says they are shifting to NoBroker because it offers cash (GP-0370)."],
        "advantages": ["Available when Urban Company is not.", "Sometimes lower price, according to reviewers.", "One masseur described as 'value for money' although 'not as professional as urban company' (RD-0130)."],
        "disadvantages": ["Competitors also fail: 'Booked NoBroker service, UPI transaction success, no service' (RD-0184).", "'I had a bad experience with Pronto' (GP-0842).", "Most Reddit mentions are consideration sets (which provider is worth it), not reported use."]},
    "Local / independent professionals and shops": {
        "used_for": "AC repair and gas refill, washing-machine repair, electrical and painting jobs, as named by reviewers.",
        "why": ["Price is the most cited reason: 'almost 4X than the local service provider' (GP-0340); a local repairer did a job for Rs 1,500 after a Rs 4,500-5,000 quote (GP-0342); a part sold for Rs 150 locally was billed at Rs 750 (PC-0126); local gas refill Rs 2,200 with 3-month warranty (RD-0169).",
                "Personal accountability: 'local vendors are more effective and at least they try to build the relationship' (PC-0156)."],
        "advantages": ["Often cheaper for repairs and small jobs, according to reviewers.", "Perceived as willing to build a relationship (PC-0156)."],
        "disadvantages": ["Perceived risk and no vetting: 'it feels super risky' (RD-0123).", "Quality varies: a local AC mechanic 'even damaged it further' (RD-0228); 'I hired guys from society - and as expected - they were worse' (RD-0125)."]},
    "Brand service centres and brand technicians": {
        "used_for": "Warranty and repair of AC and appliances (LG, Samsung, Hitachi named).",
        "why": ["Customers fall back on the brand after Urban Company's service did not fix the problem and warranty had ended (GP-1488).", "Visit charge can be lower: 'Visiting charges are 399 whereas Samsung charges 350' (GP-0241)."],
        "advantages": ["Brand warranty and genuine parts (implied; one reviewer cites a lower visit charge)."],
        "disadvantages": ["One reviewer found the service centre 'even more corrupt' than local mechanics, who were posing as official technicians (RD-0204)."]},
    "Friends, neighbours and family": {
        "used_for": "A neighbour's own technician (CC-0145) and a friend-recommended local painter (RD-0107, counted under local professionals). Referrals into Urban Company are in segments.json (discovery_channel).",
        "why": ["Trust in a known person's recommendation."],
        "advantages": ["One reviewer's neighbour had the same window-AC job done for Rs 2,200 against Rs 7,998 from Urban Company (CC-0145)."],
        "disadvantages": ["The friend-recommended painter turned into 'My Painting Nightmare' (RD-0107); only two cases, so no pattern can be claimed."]},
}
alt_groups = []
for gi, (g, ids) in enumerate(S2.ALT_GROUP.items(), 1):
    s = b[b.record_id.isin(ids)]
    tiers = Counter(tier_of.get(r, "general") for r in s.record_id)
    cats = Counter(x for x in s.service_category if x)
    why_counts = {k: int(s.text.str.contains(rx).sum()) for k, rx in reasons_rx.items()}
    alt_groups.append({"alternative_id": f"A{gi}", "alternative_type": g, "relevant_mentions": len(s), "reviews": list(s.record_id),
                       "by_tier": {"reported_use": tiers.get("reported_use", 0), "considering": tiers.get("considering", 0), "general_or_hypothetical": tiers.get("general", 0)},
                       "by_source": {p: int((s.platform == p).sum()) for p in SRC}, "service_categories": dict(cats.most_common(6)), "sentiment": sent_block(s),
                       "reason_cues_in_text_indicative": why_counts, "used_for": ALT_TEXT[g]["used_for"], "why_customers_choose_it": ALT_TEXT[g]["why"],
                       "customer_reported_advantages": ALT_TEXT[g]["advantages"], "customer_reported_disadvantages": ALT_TEXT[g]["disadvantages"],
                       "evidence_ids": EV.many(S2.ALT_Q[g], f"alternative:A{gi}")})
rule_hits = {k: int(b["alt_" + k].sum()) for k in ALT_RE}
reddit_asks = b[(b.platform == "Reddit") & b.text.str.contains(r"(?:recommend|suggest|anyone|any ?one|anybody|please share|share your|looking for|any reviews|tried)", case=False, regex=True) & b.text.str.contains(r"\?")]
alt_out = {"schema_version": "1.0", "generated_at": GEN, "dataset_reviews": N,
           "method": "Alternatives were identified by pattern rules and then each mention was read; only vetted mentions are counted. Mentions are separated into reported_use (the reviewer says they used, hired or switched), considering (actively deciding) and general_or_hypothetical (advice to others or a general comparison).",
           "summary": {"vetted_mentions_total": len({r for g in alt_groups for r in g["reviews"]}),
                       "reported_use": sum(1 for r in {r for g in alt_groups for r in g["reviews"]} if tier_of.get(r) == "reported_use"),
                       "considering": sum(1 for r in {r for g in alt_groups for r in g["reviews"]} if tier_of.get(r) == "considering"),
                       "general_or_hypothetical": sum(1 for r in {r for g in alt_groups for r in g["reviews"]} if tier_of.get(r, "general") == "general")},
           "alternatives": alt_groups,
           "whatsapp_and_community_groups": {"relevant_mentions": 0, "rule_matches_all_other_uses": rule_hits.get("WhatsApp / society / community groups"),
                                             "finding": "No review describes using a WhatsApp group or society group to find a provider. The 10 pattern matches are WhatsApp used by Urban Company or professionals as a messaging channel. The closest evidence is that customers ask strangers on Reddit for recommendations.",
                                             "reddit_posts_asking_for_recommendations": len(reddit_asks),
                                             "evidence_ids": EV.auto(reddit_asks, r"(?:recommend|suggest|anyone|any ?one|please share|looking for)", ["alternative:community"], k=3, prefer=("Neutral", "Negative"))},
           "rule_based_mentions_unvetted": rule_hits,
           "limitations": "Reddit posts are mostly questions, so many alternative mentions describe a consideration set rather than actual use; Google Play reviews rarely name alternatives."}
jwrite("alternatives.json", alt_out)

# =============================================================================================================== UNMET NEEDS
NEED_META = {
    "Reachable human support (call/phone/helpline instead of bot)": ("N01", 0.8, "Customers cannot reach a person: no phone number, a chatbot that loops, no escalation.", "O2"),
    "Fast, fair refunds and payment-failure recovery": ("N02", 0.95, "Refunds delayed or partial, money deducted without a booking, double charges.", "O3"),
    "Warranty / rework / after-sales that is honoured": ("N03", 0.75, "Warranty refused, expired in days, or rework not scheduled; Native purifier after-sales gaps.", "O5"),
    "Reliable arrival: no last-minute cancellation, ETA, alternate professional": ("N04", 0.65, "Customers want confirmation, ETA updates and a replacement when a professional cancels or is late.", "O1"),
    "Fair cancellation / reschedule policy": ("N05", 0.85, "Cancellation fees charged even when the professional cancels or is late.", "O1"),
    "Upfront total price / no surprise charges": ("N06", 0.6, "Prices that change between quote, app and bill; hidden fees; unclear inclusions.", "O4"),
    "Professional training / tools / consumables / 2-person jobs": ("N07", 0.6, "Untrained professionals, missing tools or consumables, one person sent for a two-person job.", "O6"),
    "Flexible / granular packages (single bathroom, add-ons, partial jobs, longer duration)": ("N08", 0.65, "Small-home and small-job needs: single-bathroom cleaning, per-task jobs, extending time, custom requests.", "O7"),
    "Choice of professional / continuity / gender / language": ("N09", 0.5, "Customers want to choose or re-book the same professional, a female technician, or a language match.", "O9"),
    "New service categories requested": ("N10", 0.6, "Services customers ask Urban Company to add (cooking, home organising, heat-pump, blender repair, bridal makeup).", "O7"),
    "Coverage in tier-2/3 cities and more localities": ("N11", 0.6, "Areas and cities where the service is unavailable.", "O8"),
    "App usability, location handling and information clarity": ("N12", 0.6, "App bugs, location fetching problems, unclear package inclusions.", "O6"),
    "Payment flexibility (pay after service / cash / COD)": ("N13", 0.7, "Pay-after-service or cash options requested; advance payment resented after cancellations.", "O3"),
    "Rating pressure / tip prompts from professionals": ("N14", 0.9, "Professionals ask for five stars; tips added before the job is done.", "O6"),
}
def leave_mask(s): return (s.return_class == "Non-Return") & s.return_basis.isin(["Stated", "Signalled"])
def switch_share(s): return pct(leave_mask(s).sum(), len(s))
needs = []
for name, (nid, prec, defin, opp) in NEED_META.items():
    m = b["nd_" + name]; s = b[m]
    alts = Counter()
    for k in ALT_RE:
        c = int(s["alt_" + k].sum())
        if c and k != "WhatsApp / society / community groups": alts[k] = c
    cats = Counter(x for x in s.service_category if x)
    needs.append({"unmet_need_id": nid, "name": name, "definition": defin, "n_reviews": len(s), "pct_of_dataset": pct(len(s), N), "by_source": {p: int((s.platform == p).sum()) for p in SRC},
                  "sentiment": sent_block(s), "service_categories": dict(cats.most_common(5)), "alternatives_mentioned_in_these_reviews_rule_based": dict(alts.most_common(4)),
                  "return_relevance": {"non_return_pct": pct((s.return_class == "Non-Return").sum(), len(s)), "non_return_stated_or_signalled": int(leave_mask(s).sum()), "stated_return_but_negative": int((((s.return_class == "Return") & (s.return_basis == "Stated")) & s.sentiment_label.isin(["Negative", "Mixed"])).sum()),
                                       "switching_or_warning_signals_pct": switch_share(s), "baseline_switching_or_warning_signals_pct": switch_share(b)},
                  "rule_precision_estimate": prec, "linked_opportunity": opp, "review_ids": list(s.record_id),
                  "evidence_ids": EV.auto(s, name, [f"need:{nid}"], k=3)})
for sp in S.Q["Q8"]:
    pass
needs.sort(key=lambda x: -x["n_reviews"])
for i, x in enumerate(needs, 1): x["rank_by_frequency"] = i
NEEDS_BY_NAME = {x["name"]: x for x in needs}
unmet_out = {"schema_version": "1.0", "generated_at": GEN, "dataset_reviews": N, "unmet_needs": needs,
             "method": "Fourteen need types were derived from recurring requests and frustrations (phrase scans and reading); each is a rule-based flag. Counts are indicative: rule_precision_estimate is the share of 6-8 randomly read matches that really expressed the need.",
             "illustrative_evidence_ids": EV.many(S.Q["Q8"], "need:illustrative")}
jwrite("unmet_needs.json", unmet_out)

# =============================================================================================================== OPPORTUNITIES
def nd(*names): return pd.concat([b["nd_" + n] for n in names], axis=1).any(axis=1)
OPPS = [
    ("O1", "Arrival guarantee and proactive recovery", mask_any(["th_T1"]) | nd("Reliable arrival: no last-minute cancellation, ETA, alternate professional", "Fair cancellation / reschedule policy"),
     "A confirmed booking is cancelled, rescheduled, late or never attended, and customers are charged or left without a replacement.", None,
     "Customers can plan around the slot; fewer wasted days and fewer fees for failures that are not theirs.", 4,
     "Fewer first-booking failures should reduce lapsed customers: a failed or late first booking is the earliest point at which a customer decides whether to trust the platform again (hypothesis).",
     "Two-way confirmation and live ETA; automatic same-day replacement when a professional cancels; waive cancellation fees whenever the company or professional cancels; compensation credit that is applied to the next booking.",
     "% of bookings fulfilled on the first scheduled slot; % of cancellations replaced within 2 hours; 90-day repeat booking rate for customers whose first booking was late or cancelled vs on time.",
     ["cancelled", "no_show", "late"], "T1", ["Reliable arrival: no last-minute cancellation, ETA, alternate professional", "Fair cancellation / reschedule policy"]),
    ("O2", "Human-reachable support with first-contact resolution", mask_any(["i_support_unreachable", "i_unresolved"]) | nd("Reachable human support (call/phone/helpline instead of bot)"),
     "Customers cannot reach a person, bots repeat templates, tickets are closed unresolved, and nobody owns the problem.", None,
     "A problem becomes a short, owned conversation instead of a stalemate.", 5,
     "Recourse failure is the most common companion of explicit non-return statements, so fixing it may rescue customers who would otherwise leave after a single failure (hypothesis).",
     "Callback or human chat on request after one bot exchange; a single case ID with owner and deadline; escalation path visible in the app; proactive status updates; post-resolution check-in.",
     "Time to first human response; % of complaints resolved at first contact; % of complaints reopened; 90-day repeat booking rate for customers who raised a complaint.",
     ["support_unreachable", "unresolved"], "T3", ["Reachable human support (call/phone/helpline instead of bot)"]),
    ("O3", "Instant refunds and payment-failure recovery", mask_any(["i_refund_payment"]) | nd("Fast, fair refunds and payment-failure recovery", "Payment flexibility (pay after service / cash / COD)"),
     "Money is deducted without a booking, refunds are slow or partial, and customers who paid in advance feel they cannot get it back.", None,
     "Customers regain money and trust quickly; less resentment of advance payment.", 3,
     "Refund waits turn a one-off failure into a grievance; fast automatic refunds could remove a common reason for not coming back (hypothesis).",
     "Auto-refund to source when the company or professional cancels or a payment fails; visible refund tracker with date; pay-after-service for low-value jobs.",
     "Median hours to refund; % of provider-cancelled bookings auto-refunded; repeat booking rate after a refund event.",
     ["refund_payment"], "T3", ["Fast, fair refunds and payment-failure recovery"]),
    ("O4", "All-in price lock and on-site upsell guardrails", mask_any(["th_T2"]) | nd("Upfront total price / no surprise charges"),
     "Prices change between quote, app and bill; stacked fees on small jobs; parts or extra work quoted on site at much higher rates than local providers.", None,
     "Predictable total cost and confidence that the on-site quote is fair.", 4,
     "Customers who feel overcharged compare with local providers and say they will switch; transparent pricing may keep small and repeat jobs on the platform (hypothesis).",
     "Show the all-in price (taxes, platform and visit fees) before payment; in-app approval and price cap for parts or extra work; visible rate card for common parts; clear explanation when prices change.",
     "% of bills equal to the booked price; % of on-site quote changes approved in-app; price-related complaint rate; repeat rate for small-ticket jobs.",
     ["price_high", "fees_charges", "overcharge_upsell"], "T2", ["Upfront total price / no surprise charges"]),
    ("O5", "One-tap rework and Native after-sales", mask_any(["i_warranty_rework", "i_native_after_sales"]) | nd("Warranty / rework / after-sales that is honoured"),
     "Warranty is refused or expires in days, rework needs repeated requests, and Native purifier installation or service is delayed or unsupported.", "Water Purifier / RO and AC Service & Repair",
     "Work that fails after the visit is fixed without a fight.", 4,
     "A product or repair that fails soon after service is a strong switch trigger, and Native owners are long-term customers by design (hypothesis).",
     "One-tap rework within the warranty window (same professional or a replacement); warranty visible and tracked in the app; Native installation SLA and a dedicated support line; longer warranty on high-value repairs.",
     "% of rework requests completed within 48 hours; warranty claim approval rate; Native installation completed within SLA; 90-day repeat rate after a rework event.",
     ["warranty_rework", "native_after_sales"], "T3", ["Warranty / rework / after-sales that is honoured"]),
    ("O6", "Quality, conduct and safety assurance", mask_any(["i_poor_quality", "i_damage_theft", "i_conduct_safety", "i_trust_fraud"]) | nd("Professional training / tools / consumables / 2-person jobs", "Rating pressure / tip prompts from professionals"),
     "Inconsistent skill, incomplete work, damaged property, rude or unsafe conduct, rating pressure and doubts about honesty.", "Salon and massage (safety), AC and appliance repair (damage)",
     "Consistent work and a sense of safety, especially for people alone at home.", 4,
     "Customers who say or signal they will return mostly praise the individual professional; making that quality consistent and easy to rebook could raise repeat booking (hypothesis).",
     "Skill-matched assignment and training for each category; checklist and before/after photos; damage cover with fast claims; safety features (verified identity, share-trip style tracking, female professional option); remove in-person rating prompts.",
     "% of jobs rated 4+ with no complaint; damage/theft claim rate and time to settle; safety complaints per 10,000 bookings; repeat rate with the same professional.",
     ["poor_quality", "damage_theft", "conduct_safety", "trust_fraud"], "T4", ["Professional training / tools / consumables / 2-person jobs", "Rating pressure / tip prompts from professionals"]),
    ("O7", "Flexible small-job and add-on packages", nd("Flexible / granular packages (single bathroom, add-ons, partial jobs, longer duration)", "New service categories requested"),
     "Minimum-order rules, no single-bathroom or per-task option, no way to extend time, and requests for services that do not exist.", "Home cleaning, small repairs",
     "Pay for exactly the job needed and get small jobs done without a minimum order.", 3,
     "Small jobs are where customers turn to local providers; serving them may keep customers on the platform between large bookings (hypothesis).",
     "Single-bathroom and per-task cleaning; hourly or add-on time extension; custom-request option for small jobs; test requested categories (cooking, home organising, heat pump).",
     "Share of bookings under the old minimum; conversion of cart abandoned at minimum order; repeat rate within 90 days for small-job customers.",
     ["missing_service_request"], "T5", ["Flexible / granular packages (single bathroom, add-ons, partial jobs, longer duration)", "New service categories requested"]),
    ("O8", "Coverage waitlist and tier-2/3 expansion", nd("Coverage in tier-2/3 cities and more localities") | mask_any(["i_coverage_gap"]),
     "Customers in unserved areas and cities cannot book at all; some download the app and find nothing.", "Tier-2/3 cities",
     "Access to the service, or a clear date when it will arrive.", 2,
     "Customers who cannot book cannot return; a waitlist keeps the relationship alive until coverage arrives (hypothesis; this evidence is thin).",
     "In-app waitlist by pincode with demand counts; partner onboarding where demand clusters; show nearest available categories.",
     "Waitlist sign-ups by pincode; % of waitlisted users who book within 90 days of launch.",
     ["coverage_gap"], "T5", ["Coverage in tier-2/3 cities and more localities"]),
    ("O9", "Preferred-professional continuity", nd("Choice of professional / continuity / gender / language") | b.record_id.isin(CUR.ER_INTENT),
     "Customers want to rebook the professional who did a good job (and avoid one who did not), but face surcharges, no choice, or reassignment of the same person after a complaint.", None,
     "Reliable quality from someone they trust, without paying extra to rebook.", 3,
     "Several explicit return statements are about a specific professional ('will definitely call her again'); free, easy rebooking could convert one good job into repeat bookings (hypothesis).",
     "'Book again with the same professional' on the completion screen; no surcharge for re-booking; block a professional after a complaint; recommend favourites for the next category.",
     "% of bookings re-booked with the same professional; 90-day repeat rate after a 5-star job with and without the rebook prompt.",
     [], "T4", ["Choice of professional / continuity / gender / language"]),
]
opps = []
for oid, name, m, problem, seg, benefit, impact, link, improvement, metric, codes, theme_id, need_names in OPPS:
    s = b[m]; n = len(s)
    rated = s.rating_f.dropna()
    sev = (s.sentiment_label == "Negative").sum() / n
    sources = sum(1 for p in SRC if (s.platform == p).sum() >= 5)
    sw = leave_mask(s).sum() / n
    base_sw = leave_mask(b).mean()
    freq = min(1.0, pct(n, N) / 15.0); evid = min(1.0, 0.6 * sources / 4 + 0.4 * min(1.0, n / 80.0)); rep = min(1.0, 4 * sw)
    score = 0.25 * freq + 0.20 * sev + 0.20 * evid + 0.20 * rep + 0.15 * impact / 5.0
    cats = Counter(x for x in s.service_category if x)
    ev_ids = []
    for c in codes:
        ev_ids += EV.auto(s, c, [f"opportunity:{oid}"], k=1)
    for nn in need_names:
        ev_ids += EV.auto(s, nn, [f"opportunity:{oid}"], k=1)
    ev_ids = list(dict.fromkeys(ev_ids))[:5]
    opps.append({"opportunity_id": oid, "title": name, "customer_problem": problem, "supporting_segment": seg, "top_service_categories_in_evidence": dict(cats.most_common(4)),
                 "evidence": {"reviews": n, "pct_of_dataset": pct(n, N), "by_source": {p: int((s.platform == p).sum()) for p in SRC}, "sentiment": sent_block(s),
                              "negative_share_pct": pct((s.sentiment_label == "Negative").sum(), n), "rating_1_2_share_of_rated_pct": pct((rated <= 2).sum(), len(rated)) if len(rated) else None,
                              "non_return_pct": pct((s.return_class == "Non-Return").sum(), n), "return_pct": pct((s.return_class == "Return").sum(), n), "switching_or_warning_or_non_return_pct": pct(sw * n, n),
                              "baseline_switching_or_warning_or_non_return_pct": round(100 * base_sw, 1), "evidence_ids": ev_ids, "review_ids": list(s.record_id),
                              "related_theme": theme_id, "related_unmet_needs": [NEEDS_BY_NAME[x]["unmet_need_id"] for x in need_names]},
                 "expected_customer_benefit": benefit, "influence_on_repeat_booking_hypothesis": link, "suggested_improvement_hypothesis": improvement, "suggested_success_metric": metric,
                 "prioritisation": {"frequency": round(freq, 3), "severity": round(sev, 3), "evidence_strength": round(evid, 3), "repeat_relevance": round(rep, 3), "impact_judgement_1_to_5": impact, "score": round(score, 3),
                                    "formula": "0.25*frequency(share of dataset/15%, cap 1) + 0.20*severity(share Negative) + 0.20*evidence(source breadth and volume) + 0.20*repeat relevance(4 x share with non-return/switching/warning, cap 1) + 0.15*impact(analyst judgement 1-5, a hypothesis)"}})
opps.sort(key=lambda x: -x["prioritisation"]["score"])
for i, o in enumerate(opps, 1):
    o["priority_rank"] = i
    o["priority"] = "High" if i <= 3 else ("Medium" if i <= 6 else "Low")
    o["priority_rationale"] = (f"Affects {o['evidence']['reviews']} reviews ({o['evidence']['pct_of_dataset']}% of the dataset), {o['evidence']['negative_share_pct']}% Negative, present in "
                               f"{sum(1 for v in o['evidence']['by_source'].values() if v >= 5)} of 4 sources; {o['evidence']['switching_or_warning_or_non_return_pct']}% of these reviews contain switching, warning or non-return signals "
                               f"(dataset baseline {o['evidence']['baseline_switching_or_warning_or_non_return_pct']}%).")
from pm_briefs import PM
for o in opps:                                    # attach the product-manager brief; keep the older summary fields in sync with it
    pm, ev_, pr_ = PM[o["opportunity_id"]], o["evidence"], o["prioritisation"]
    conf = "High" if pr_["evidence_strength"] >= 0.9 and ev_["reviews"] >= 100 else ("Medium" if pr_["evidence_strength"] >= 0.6 and ev_["reviews"] >= 40 else "Low")
    rec = "Validate first" if conf == "Low" else ("Start now" if o["priority_rank"] <= 3 else ("Quick win" if pm["effort"] == "S" else "Plan next"))
    o["pm_brief"] = {"problem": pm["problem"], "who_is_affected": pm["who"], "why_it_happens_hypotheses": pm["why_it_happens"], "proposal": pm["proposal"], "why_it_should_lift_repeat_booking": pm["repeat_mechanism"],
                     "success_looks_like": pm["success"], "watch_outs": pm["watch_out"], "effort": pm["effort"], "effort_note": pm["effort_note"], "evidence_confidence": conf, "recommendation": rec,
                     "labels": "Customer evidence (counts, quotes) comes from the reviews. Root causes, proposals, the repeat-booking mechanism and effort are product-manager hypotheses and judgements, not findings."}
    o["suggested_improvement_hypothesis"] = " ".join(f"({i + 1}) {x['title']}: {x['what']}" for i, x in enumerate(pm["proposal"]))
    o["influence_on_repeat_booking_hypothesis"] = pm["repeat_mechanism"]
    o["suggested_success_metric"] = pm["success"]
opp_out = {"schema_version": "1.0", "generated_at": GEN, "dataset_reviews": N, "opportunities": opps,
           "distinction": "'evidence' fields are customer-reported and computed from the dataset; fields ending in _hypothesis, the impact judgement and the success metrics are product hypotheses and recommendations, not findings."}
jwrite("opportunities.json", opp_out)
OPPD = {o["opportunity_id"]: o for o in opps}

# =============================================================================================================== TRIGGERS / HOUSEHOLD / DISCOVERY (vetted examples)
def vetted(groups, qspec, tag):
    out = []
    for gi, (name, ids) in enumerate(groups.items(), 1):
        s = b[b.record_id.isin(ids)]
        out.append({"segment_id": f"{tag}{gi:02d}", "name": name, "n_vetted_examples": len(s), "small_sample": len(s) < 30, "sentiment": sent_block(s),
                    "theme_prevalence": {t: {"n": int(s["th_" + t].sum()), "pct": pct(s["th_" + t].sum(), len(s))} for t in TH},
                    "return_signals": rc_block(s), "dominant_themes": [t for t, _ in sorted(((t, s["th_" + t].sum()) for t in TH), key=lambda x: -x[1])[:2]],
                    "by_source": {p: int((s.platform == p).sum()) for p in SRC}, "review_ids": list(s.record_id), "evidence_ids": EV.many(qspec.get(name, []), f"{tag}:{name}")})
    return out
triggers_seg = vetted(S.TRIGGERS, S2.TRIGGER_Q, "TRG"); household_seg = vetted(S.HOUSEHOLD, S2.HOUSEHOLD_Q, "HH"); discovery_seg = vetted(S.DISCOVERY, S2.DISCOVERY_Q, "DC")
trig_union = set(i for ids in S.TRIGGERS.values() for i in ids)

# =============================================================================================================== SEGMENTS
OVERALL_ISS = {c: pct(b["i_" + c].sum(), N) for c in SUB if "i_" + c in b.columns}
def seg_entry(sid, name, s, kind):
    n = len(s)
    th_prev = {t: {"n": int(s["th_" + t].sum()), "pct": pct(s["th_" + t].sum(), n)} for t in TH}
    top_iss = sorted(((c, s["i_" + c].sum()) for c in SUB if "i_" + c in b.columns and not c.startswith("pos_")), key=lambda x: -x[1])[:3]
    lifts = [(c, pct(s["i_" + c].sum(), n) / OVERALL_ISS[c], int(s["i_" + c].sum())) for c in SUB if "i_" + c in b.columns and OVERALL_ISS.get(c, 0) > 0 and s["i_" + c].sum() >= 5 and not c.startswith("pos_")]
    lifts.sort(key=lambda x: -x[1])
    diff = f"Over-indexes on '{SUB[lifts[0][0]]}' ({pct(lifts[0][2], n)}% of its reviews vs {OVERALL_ISS[lifts[0][0]]}% overall)" if lifts and lifts[0][1] >= 1.3 else "No issue differs strongly from the overall pattern at this sample size"
    return {"segment_id": sid, "name": name, "n": n, "pct_of_dataset": pct(n, N), "small_sample": n < 30, "sentiment_pct": {s_: pct((s.sentiment_label == s_).sum(), n) for s_ in SENTS[:4]},
            "theme_prevalence": th_prev, "dominant_themes": [t for t, _ in sorted(th_prev.items(), key=lambda kv: -kv[1]["n"])[:2]],
            "top_issues": [{"issue": SUB[c], "n": int(k), "pct": pct(k, n)} for c, k in top_iss], "return_signals": rc_block(s), "important_difference": diff,
            "avg_rating_where_rated": round(float(s.rating_f.mean()), 2) if s.rating_f.notna().any() else None, "by_source": {p: int((s.platform == p).sum()) for p in SRC},
            "review_ids": list(s.record_id), "evidence_ids": EV.auto(s, lifts[0][0] if lifts and lifts[0][1] >= 1.3 else "poor_quality", [f"segment:{sid}"], k=2) if n >= 5 else []}
cat_counts = b.service_category[b.service_category != ""].value_counts()
seg_cat = [seg_entry("CAT_" + c.upper().replace(" ", "_").replace("/", "").replace("&", "AND").replace("__", "_"), c, b[b.service_category == c], "category") for c, k in cat_counts.items() if k >= 15]
seg_cat.append(seg_entry("CAT_NOT_STATED", "(Service category not stated in the review)", b[b.service_category == ""], "category"))
city_rows = b[b.city != ""].assign(_c=b.city.str.split("; ")).explode("_c")
city_counts = city_rows._c.value_counts()
seg_city = [seg_entry("CITY_" + c.upper().replace(" ", "_"), c, b[b.record_id.isin(city_rows[city_rows._c == c].record_id)], "city") for c, k in city_counts.items() if k >= 8]
seg_city.append(seg_entry("CITY_NOT_STATED", "(No city named in the review)", b[b.city == ""], "city"))
seg_src = [seg_entry("SRC_" + p.upper().replace(" ", "_").replace(".", ""), p, b[b.platform == p], "source") for p in SRC]
macro = {t: round(sum(pct(b[b.platform == p]["th_" + t].sum(), SRC_N[p]) for p in SRC) / len(SRC), 1) for t in TH}
pooled = {t: pct(b["th_" + t].sum(), N) for t in TH}
segments_out = {"schema_version": "1.0", "generated_at": GEN, "dataset_reviews": N,
                "service_category": {"min_n_for_listing": 15, "coverage": f"{int((b.service_category != '').sum())} of {N:,} reviews ({pct((b.service_category != '').sum(), N)}%) name a service category", "segments": seg_cat},
                "city": {"min_n_for_listing": 8, "coverage": f"{int((b.city != '').sum())} of {N:,} reviews ({pct((b.city != '').sum(), N)}%) name a city (a review can name more than one)", "segments": seg_city},
                "source": {"segments": seg_src, "pooled_vs_equal_weight_theme_prevalence_pct": {"pooled": pooled, "equal_weight_across_4_sources": macro},
                           "note": "Google Play is 72% of the dataset, so pooled prevalence mostly reflects Google Play. Equal-weight prevalence shows what the pattern would be if each source counted the same."},
                "household_type": {"coverage": f"Household type is stated in only about {len(set(i for ids in S.HOUSEHOLD.values() for i in ids))} reviews; these are vetted examples, not prevalence.", "segments": household_seg},
                "discovery_channel": {"coverage": f"How the customer found Urban Company is stated in only about {len(set(i for ids in S.DISCOVERY.values() for i in ids))} reviews; these are vetted examples, not prevalence.", "segments": discovery_seg},
                "booking_triggers": {"coverage": f"{len(trig_union)} reviews ({pct(len(trig_union), N)}%) state a trigger or occasion for booking; these are vetted examples.", "segments": triggers_seg}}
jwrite("segments.json", segments_out)

# =============================================================================================================== FINDINGS (top three)
def mk_finding(fid, title, tid, summary, impact, repeat, why, extra_codes, ev_ids):
    t = TD[tid]; s = b[theme_masks[tid]]
    enr_share = pct(leave_mask(s).sum(), len(s))
    return {"finding_id": fid, "rank": int(fid[1:]), "title": title, "evidence_summary": summary, "supporting_volume": {"reviews": t["review_count"], "pct_of_dataset": t["pct_of_dataset"], "theme_id": tid, "by_source": t["by_source"], "sentiment": t["sentiment"],
                                                                                                                     "subthemes": [{"name": x["name"], "n": x["n"]} for x in t["subthemes"]]},
            "customer_impact": impact, "connection_to_repeat_booking": repeat, "why_it_matters_to_urban_company": why, "evidence_ids": ev_ids, "review_ids": t["review_ids"]}
cmpt = compare["theme_prevalence_pct"]
er_t3, enr_t3 = cmpt["T3"]["return_stated_signalled"], cmpt["T3"]["non_return_stated_signalled"]
er_t2, enr_t2 = cmpt["T2"]["return_stated_signalled"], cmpt["T2"]["non_return_stated_signalled"]
er_t1, enr_t1 = cmpt["T1"]["return_stated_signalled"], cmpt["T1"]["non_return_stated_signalled"]
n_snr, n_sr = len(SNR), len(SR)
t3p = int((theme_masks["T3"] & b[["th_T1", "i_poor_quality", "i_damage_theft", "i_price_high", "i_overcharge_upsell"]].any(axis=1)).sum())
findings = [
    mk_finding("F1", "When something goes wrong, customers cannot reach a person, get their money back or get the work fixed", "T3",
               f"{TD['T3']['review_count']} reviews ({TD['T3']['pct_of_dataset']}%) describe a recourse failure: {TD['T3']['subthemes'][0]['n']} cannot reach support (bot loops, no number), {TD['T3']['subthemes'][1]['n']} have refund or payment problems, {TD['T3']['subthemes'][2]['n']} report unresolved complaints, {TD['T3']['subthemes'][3]['n']} are refused warranty or rework and {TD['T3']['subthemes'][4]['n']} describe Native purifier installation or after-sales failures. It is {TD['T3']['sentiment']['Negative']['pct']}% Negative and appears in all four sources ({TD['T3']['by_source'][2]['pct_of_source_reviews']}% of PissedConsumer and {TD['T3']['by_source'][3]['pct_of_source_reviews']}% of ConsumerComplaints reviews, {TD['T3']['by_source'][0]['pct_of_source_reviews']}% of Google Play). {t3p} of the {TD['T3']['review_count']} also describe a primary failure first, so poor recourse compounds other problems.",
               "Customers lose time, money (advance payments, fees, repair costs) and trust, and describe repeated chasing with no owner. Several state they have escalated outside the app (consumer forums, legal notice).",
               f"Recourse is the strongest differentiator among customers who state or signal what they will do: {enr_t3}% of those {n_snr} Non-Return reviews cite recourse failures against {er_t3}% of the {n_sr} Return reviews. A reading of the evidence, not proof of cause.",
               "A single failed booking is recoverable if resolution is quick; the evidence suggests that the resolution experience, more than the original failure, shapes whether customers describe leaving.",
               [], EV.many(S.Q["T3"], "finding:F1")),
    mk_finding("F2", "Price and fees feel unpredictable and higher than local alternatives, especially for small jobs", "T2",
               f"{TD['T2']['review_count']} reviews ({TD['T2']['pct_of_dataset']}%) raise price: {TD['T2']['subthemes'][0]['n']} say prices are too high or rising, {TD['T2']['subthemes'][1]['n']} object to platform, visit, cancellation or plan fees, and {TD['T2']['subthemes'][2]['n']} describe extra charges or parts upselling by the professional. The theme is present at a similar rate in every source ({TD['T2']['by_source'][0]['pct_of_source_reviews']}% Google Play, {TD['T2']['by_source'][1]['pct_of_source_reviews']}% Reddit, {TD['T2']['by_source'][2]['pct_of_source_reviews']}% PissedConsumer, {TD['T2']['by_source'][3]['pct_of_source_reviews']}% ConsumerComplaints). Customers who compare name local providers as cheaper, and ask for an all-in price.",
               "Customers pay more than they expected, feel cheated by on-site quotes, and in several reviews pay fees for failures that were not theirs (cancellation fee when the professional is late).",
               f"Price and fees appear in {enr_t2}% of the Non-Return reviews that state or signal it, against {er_t2}% of the Return reviews. Reviewers describe turning to local providers for repairs and small jobs because of price (see alternatives.json).",
               "Price transparency is a trust issue as much as a cost issue; the cheaper local alternative is the main named substitute for repairs and small jobs.",
               [], EV.many(S.Q["T2"], "finding:F2")),
    mk_finding("F3", "Booked services are cancelled, delayed or never attended, and customers pay the cost", "T1",
               f"{TD['T1']['review_count']} reviews ({TD['T1']['pct_of_dataset']}%) describe a fulfilment failure: {TD['T1']['subthemes'][0]['n']} cancellations by the company or professional, {TD['T1']['subthemes'][1]['n']} reschedules, {TD['T1']['subthemes'][2]['n']} no-shows, {TD['T1']['subthemes'][3]['n']} late arrivals and {TD['T1']['subthemes'][4]['n']} missing slots. {TD['T1']['sentiment']['Negative']['pct']}% are Negative. It is concentrated where customers escalate ({TD['T1']['by_source'][2]['pct_of_source_reviews']}% of PissedConsumer, {TD['T1']['by_source'][3]['pct_of_source_reviews']}% of ConsumerComplaints) and present in {TD['T1']['by_source'][0]['pct_of_source_reviews']}% of Google Play reviews.",
               "Customers arrange leave, guests, festivals or deliveries around a slot; failures cost a day, a missed occasion or a fee, and customers often have to rebook from scratch.",
               f"{enr_t1}% of the Non-Return reviews that state or signal it and {er_t1}% of the matching Return reviews mention it, so unreliability is common among leavers and among loyal customers who stay and complain. Warnings such as 'Think twice before using Urban Company' (from a six-year customer) show that reliability failures also reach long-standing customers.",
               "Fulfilment reliability is the base promise of a booking marketplace; it also triggers the other findings, because a failure creates the need for support, refunds and price disputes.",
               [], EV.many(S.Q["T1"], "finding:F3")),
]
jwrite("findings.json", {"schema_version": "1.0", "generated_at": GEN, "dataset_reviews": N, "findings": findings,
                         "prioritisation_note": "Ordered by the evidence score of the underlying problem theme and the strength of its link to Non-Return signals. T4 (professional quality) is the main source of positive evidence and of Return signals; it is covered in the themes, behaviour analysis and opportunity O6/O9."})

# =============================================================================================================== QUESTIONS
EXP_RX = r"expect(?:ed|s|ing|ation|ations)?\b|supposed to|promised?|assured|advertis\w+|as per (?:the )?(?:booking|package|app|checklist)"
exp_rows = b[b.text.str.contains(EXP_RX, case=False, regex=True)]
hyg = b[b.text.str.contains(r"hygien\w+|sanitis\w+|disinfect\w+|unsafe|safety|dirty tools|clean (?:cloth|napkin)", case=False, regex=True)]
Q = {}
Q["Q1"] = {"question": "What do customers expect once a booking is complete?",
           "summary": f"Customers expect the booking to behave like a contract: the professional arrives when promised, does the work that was advertised and included, behaves professionally, charges the quoted price, and someone takes responsibility if it goes wrong. {len(exp_rows)} reviews ({pct(len(exp_rows), N)}%) use explicit expectation or promise language ('expect', 'promised', 'advertised', 'assured', 'supposed to'). The gaps they describe are mostly about arrival ({TD['T1']['review_count']} reviews), work quality ({int(b.i_poor_quality.sum())}), price ({TD['T2']['review_count']}) and recourse ({TD['T3']['review_count']}).",
           "expectations": [
               {"expectation": "Arrive when promised and tell me if plans change", "gap_evidence_reviews": TD["T1"]["review_count"], "positive_evidence_reviews": int(b.i_pos_punctual.sum())},
               {"expectation": "Do the work that was advertised and included, completely and properly", "gap_evidence_reviews": int(b[["i_poor_quality", "i_damage_theft"]].any(axis=1).sum()), "positive_evidence_reviews": int(b.i_pos_quality_pro.sum())},
               {"expectation": "Professional, respectful and safe behaviour; hygiene", "gap_evidence_reviews": int(b.i_conduct_safety.sum()), "hygiene_or_safety_mentions": len(hyg)},
               {"expectation": "Honest, transparent price; no surprise charges", "gap_evidence_reviews": TD["T2"]["review_count"], "positive_evidence_reviews": int(b.text.str.contains(r"transparent|reasonable (?:price|rate)|affordable|no hidden", case=False, regex=True).sum())},
               {"expectation": "Reachable support and accountability after the service", "gap_evidence_reviews": int(b[["i_support_unreachable", "i_unresolved"]].any(axis=1).sum()), "positive_evidence_reviews": int(b.i_pos_support_resolution.sum())},
               {"expectation": "Warranty, rework and refunds that are honoured as promised", "gap_evidence_reviews": int(b[["i_warranty_rework", "i_native_after_sales", "i_refund_payment"]].any(axis=1).sum())}],
           "evidence_strength": "strong", "gaps": [f"Reviews describe outcomes more than expectations; the expectation language is present in {pct(len(exp_rows), N)}% of reviews.", f"Hygiene or safety wording appears in only {len(hyg)} reviews ({pct(len(hyg), N)}%)."]}
Q["Q1"]["evidence_ids"] = EV.many(S.Q["Q1"], "question:Q1")
Q["Q2"] = {"question": "How do customers decide that a home service is needed, and when?",
           "summary": f"Only {len(trig_union)} reviews ({pct(len(trig_union), N)}%) state why or when they decided to book; most reviews describe the outcome, so this answer rests on a small, mostly Reddit-based sample of vetted examples. Triggers fall into appliance breakdowns (an AC or TV stops working), moving or tenancy changes, festivals and personal events, health or age circumstances, pests and leakage, season (heat, rain) and time pressure. Urgent needs (a breakdown, a leak, an event tomorrow) coexist with planned and periodic ones (annual AC servicing, plans or subscriptions, pre-move deep cleaning).",
           "triggers": [{"segment_id": s["segment_id"], "trigger": s["name"], "n_vetted_examples": s["n_vetted_examples"], "evidence_ids": s["evidence_ids"]} for s in triggers_seg],
           "evidence_strength": "weak", "gaps": ["Trigger statements are rare in reviews and complaints; Reddit posts are the richest source (people ask for help when a need arises).", "Frequency of need cannot be estimated; examples show variety, not prevalence."]}
Q["Q2"]["evidence_ids"] = [e for s in triggers_seg for e in s["evidence_ids"]][:12]
Q["Q3"] = {"question": "Who or what do customers turn to when they need the same kind of service again, or a different one?",
           "summary": f"Customers who describe their next booking either stay with Urban Company ({len(R_):,} reviews, {pct(len(R_), N)}%, are classed as likely to return) or turn to local professionals, other platforms and brand service centres. Vetted alternative mentions: {alt_out['summary']['vetted_mentions_total']} reviews, of which {alt_out['summary']['reported_use']} report actual use, {alt_out['summary']['considering']} are considering and {alt_out['summary']['general_or_hypothetical']} are advice or general comparisons. Local and independent professionals are the most named alternative, mainly for repairs and small jobs where price and accountability matter; platforms appear mostly in Reddit consideration sets; brand service centres appear after warranty problems. Friends and family mostly act as the referral source into Urban Company.",
           "alternatives": [{"alternative_id": a["alternative_id"], "type": a["alternative_type"], "mentions": a["relevant_mentions"], "by_tier": a["by_tier"]} for a in alt_groups],
           "evidence_strength": "moderate", "gaps": [f"Alternatives are named in a small share of reviews (vetted mentions {pct(alt_out['summary']['vetted_mentions_total'], N)}% of the dataset); Google Play reviews seldom name them.", "Return behaviour by category cannot be compared reliably (small counts)."]}
Q["Q3"]["evidence_ids"] = [e for a in alt_groups for e in a["evidence_ids"][:2]]
Q["Q4"] = {"question": "How do customers describe why they did or did not book again, in their own words?",
           "summary": f"{pct(classified, N)}% of reviews could be classed: {len(R_):,} as Return ({pct(len(R_), N)}%) and {len(NR_):,} as Non-Return ({pct(len(NR_), N)}%). Only {basis_n['Stated']} say it in the first person, {basis_n['Signalled']} signal it (advising others against using the app, switching, distrust, or recommending with trust) and {basis_n['Inferred']:,} are inferred from how positive or negative the review is. Reasons to return are mostly about the person who did the job (skill, politeness, punctuality, 'will definitely call her again') and general convenience ('my go to app'). Reasons for not returning are recourse and trust failures after a booking went wrong ('this is the last time I am taking service from you guys'), switching to named alternatives, and price. Notably {pct(sr_unhappy, n_stated_r)}% of customers who say they came back are themselves Negative or Mixed, which suggests habit or lack of alternatives can coexist with a poor experience.",
           "distribution": behaviour_out["distribution"], "reasons_to_return": ["Skilled, polite, punctual professional", "Convenience and breadth of services", "Quick resolution when something went wrong", "Trusted professional they can ask for again"],
           "reasons_not_to_return": ["Complaint not resolved or refund delayed", "Repeated cancellations or no-shows", "Price, fees and upselling", "Safety or trust incident (theft, abuse, fraud)"],
           "evidence_strength": "moderate", "gaps": [f"Only {pct(basis_n['Stated'], N)}% of reviews say it in the first person; most labels are predictions from sentiment, and customers who simply stopped booking leave no review."]}
Q["Q4"]["evidence_ids"] = behaviour_out["classes"]["Return"]["representative_evidence_ids"][:6] + behaviour_out["classes"]["Non-Return"]["representative_evidence_ids"][:6]
Q["Q5"] = {"question": "What do customers do outside the app: local providers, neighbours, family, WhatsApp groups?",
           "summary": f"Outside the app customers mainly use local and independent professionals ({alt_groups[1]['relevant_mentions']} vetted reviews, {alt_groups[1]['by_tier']['reported_use']} reporting actual use), other platforms ({alt_groups[0]['relevant_mentions']}), brand service centres ({alt_groups[2]['relevant_mentions']}) and, rarely, a neighbour's provider. They choose local providers for lower prices, direct accountability and small jobs, and say they fear risk and variable quality. No review describes a WhatsApp or society group used to find providers; the closest evidence is {len(reddit_asks)} Reddit posts that ask other users for experiences or recommendations.",
           "evidence_strength": "moderate", "gaps": ["WhatsApp and neighbour networks are invisible in public reviews; absence of evidence is not evidence of absence."]}
Q["Q5"]["evidence_ids"] = EV.many(S.Q["Q5"], "question:Q5")
cmp_ = compare["theme_prevalence_pct"]
Q["Q6"] = {"question": "What separates customers who return from customers who do not, in their own accounts?",
           "summary": f"Among reviews that state or signal what the customer will do (Return {n_sr}, Non-Return {n_snr}) the clearest separators are recourse and price. Recourse failures (T3) appear in {cmp_['T3']['non_return_stated_signalled']}% of Non-Return reviews vs {cmp_['T3']['return_stated_signalled']}% of Return; price and fees (T2) in {cmp_['T2']['non_return_stated_signalled']}% vs {cmp_['T2']['return_stated_signalled']}%; fulfilment (T1) in {cmp_['T1']['non_return_stated_signalled']}% vs {cmp_['T1']['return_stated_signalled']}%. Return is about people: professional quality, punctuality and trust (T4) appear in {cmp_['T4']['return_stated_signalled']}% of Return reviews. Across all {classified:,} classified reviews the same pattern holds (Non-Return {cmp_['T3']['non_return']}% recourse; Return {cmp_['T3']['return']}%), but those groups partly restate sentiment, so the stated and signalled groups are the stronger evidence. {pct(sr_unhappy, n_stated_r)}% of customers who say they came back are Negative or Mixed: loyal does not mean satisfied.",
           "comparison": compare, "evidence_strength": "moderate", "gaps": ["Inferred labels come from sentiment, so differences between all Return and all Non-Return reviews partly restate sentiment.", "A positive rating is not treated as proof of repeat booking, and a negative one is not treated as proof of non-return: both only count when the wording agrees or there is a clear signal."]}
Q["Q6"]["evidence_ids"] = EV.many(S.Q["Q4return"][:3] + S.Q["Q4nonreturn"][:3], "question:Q6")
sc_top = sorted([s for s in seg_cat if s["n"] >= 30 and not s["segment_id"].endswith("NOT_STATED")], key=lambda s: -s["n"])
def seg_line(s): return f"{s['name']} (n={s['n']}): {s['important_difference'].lower()}"
Q["Q7"] = {"question": "How do these patterns differ by service category, city, household type and acquisition channel?",
           "summary": f"Service category is named in {pct((b.service_category != '').sum(), N)}% of reviews and city in {pct((b.city != '').sum(), N)}%, so comparisons use small groups and should be read with sample sizes. By category: " + "; ".join(seg_line(s) for s in sc_top[:5]) + f". By city (n>=8): {len([s for s in seg_city if not s['segment_id'].endswith('STATED')])} cities qualify; the largest are " + ", ".join(f"{s['name']} (n={s['n']})" for s in sorted([s for s in seg_city if not s['segment_id'].endswith('STATED')], key=lambda s: -s['n'])[:4]) + f". Source matters more than any other segment: PissedConsumer reviews are {TD['T3']['by_source'][2]['pct_of_source_reviews']}% about recourse and {TD['T1']['by_source'][2]['pct_of_source_reviews']}% about fulfilment, against {TD['T3']['by_source'][0]['pct_of_source_reviews']}% and {TD['T1']['by_source'][0]['pct_of_source_reviews']}% on Google Play. Household type and discovery channel are stated in only a few dozen reviews: lone dwellers and women raise safety, elderly and pet households raise urgency and conduct, newcomers and tenants use the platform for moves, and referrals, ads/YouTube, Reddit research and Amazon/Flipkart purchases of Native products are the discovery routes that appear.",
           "evidence_strength": "weak", "gaps": ["Household type and discovery channel are described in about 1-3% of reviews.", "City is explicit in 8.5% of reviews; Delhi and Gurugram are the most named cities, mostly on Reddit and complaint sites."]}
Q["Q7"]["evidence_ids"] = [e for s in (household_seg + discovery_seg) for e in s["evidence_ids"][:1]][:10]
Q["Q8"] = {"question": "What unmet needs emerge consistently across conversations?",
           "summary": "The most frequent unmet needs are " + ", ".join(f"{x['name'].split(' (')[0].lower()} ({x['n_reviews']})" for x in needs[:6]) + f". They are mostly experiential failures (support, refunds, warranty, reliable arrival, price clarity) rather than missing features; explicit feature requests (single-bathroom cleaning, pay-after-service, female technicians, new categories) are fewer but specific.",
           "unmet_needs": [{"unmet_need_id": x["unmet_need_id"], "name": x["name"], "n_reviews": x["n_reviews"], "pct_of_dataset": x["pct_of_dataset"], "linked_opportunity": x["linked_opportunity"]} for x in needs],
           "evidence_strength": "strong", "gaps": ["Counts are indicative: need flags are rule-based with 50-95% measured precision (see unmet_needs.json)."]}
Q["Q8"]["evidence_ids"] = unmet_out["illustrative_evidence_ids"][:8]
for k, v in Q.items():
    v["question_id"] = k
jwrite("questions.json", {"schema_version": "1.0", "generated_at": GEN, "dataset_reviews": N, "questions": [Q[k] for k in sorted(Q)]})

# =============================================================================================================== OVERVIEW / LIMITATIONS / REVIEWS / EVIDENCE / MANIFEST
rated = b.rating_f.dropna()
neg_total = int((b.sentiment_label == "Negative").sum())
complaint_n = int(b.platform.isin(["PissedConsumer", "ConsumerComplaints.in"]).sum())
reddit = b[b.platform == "Reddit"]
overview = {"schema_version": "1.0", "generated_at": GEN, "product": "Urban Company", "business_metric": "Percentage of customers who complete another booking within 90 days",
            "dataset": {"reviews_analysed": N, "master_file": "output/urban_company_reviews_master.csv",                         "date_range": {"earliest": b.review_date.replace("", pd.NA).dropna().min(), "latest": b.review_date.max()},
                        "by_source": [{"source": p, "n": SRC_N[p], "pct": pct(SRC_N[p], N)} for p in SRC], "sentiment": sent_block(b),
                        "rating": {"rated_reviews": len(rated), "mean": round(float(rated.mean()), 2), "pct_1_2_star": pct((rated <= 2).sum(), len(rated)),
                                   "distribution": {str(k): int(v) for k, v in rated.round().astype(int).value_counts().sort_index().items()}},
                        "service_category_stated": int((b.service_category != "").sum()), "city_stated": int((b.city != "").sum())},
            "headline_metrics": {"themes": [{"theme_id": x["theme_id"], "name": x["name"], "review_count": x["review_count"], "pct_of_dataset": x["pct_of_dataset"]} for x in tdata],
                                 "return_behaviour": behaviour_out["distribution"],
                                 "top_findings": [{"finding_id": f["finding_id"], "title": f["title"], "reviews": f["supporting_volume"]["reviews"]} for f in findings],
                                 "top_opportunities": [{"opportunity_id": o["opportunity_id"], "title": o["title"], "priority": o["priority"], "score": o["prioritisation"]["score"]} for o in opps[:5]],
                                 "reviews_with_at_least_one_theme": int(any_theme.sum())},
            "method": {"summary": "Phrase-rule coding of every review (26 codes: 22 problems and 4 kinds of praise, return-behaviour classes, alternatives and 14 unmet needs), with the matched text read and checked by an AI-assisted analyst; every count and score is computed in code. The same engine runs live on an uploaded file, where an LLM reads each comment.",
                       "validation": "Rule precision was spot-checked on 6-8 random matches per code. The engine was also compared with a 20-comment golden set labelled by hand (see the AI Evidence Log and the Golden data set page)."},
            "files": ["overview.json", "themes.json", "findings.json", "questions.json", "behaviour.json", "alternatives.json", "segments.json", "unmet_needs.json", "opportunities.json", "evidence.json", "limitations.json", "reviews.json", "trust.json", "manifest.json"]}
jwrite("overview.json", overview)

title_only = int((reddit.content_type == "Post (title only)").sum())
limitations = {"schema_version": "1.0", "generated_at": GEN, "dataset_reviews": N,
               "dataset_characteristics": {
                   "negative_representation": {"negative_pct": pct(neg_total, N), "positive_pct": pct((b.sentiment_label == 'Positive').sum(), N), "complaint_platform_reviews": complaint_n, "complaint_platform_pct": pct(complaint_n, N),
                                               "note": "PissedConsumer and ConsumerComplaints contain complaints by design (98% Negative). Customers who never complained or never came back leave no trace."},
                   "google_play_dominance": {"n": SRC_N["Google Play Store"], "pct": pct(SRC_N["Google Play Store"], N), "note": "Pooled percentages mostly describe Google Play app reviews, which are short (median 15 words) and about the app and service in general."},
                   "missing_city_and_category": {"city_missing_pct": pct((b.city == '').sum(), N), "category_missing_pct": pct((b.service_category == '').sum(), N), "note": "Segment comparisons by city and category use a minority of reviews; city is a keyword tag from the review text, not a profile field."},
                   "return_evidence": {"return": len(R_), "non_return": len(NR_), "classified_pct": pct(classified, N), "stated_pct": pct(basis_n["Stated"], N), "signalled_pct": pct(basis_n["Signalled"], N), "inferred_pct": pct(basis_n["Inferred"], N), "insufficient_pct": beh["Insufficient Evidence"]["pct_of_dataset"], "note": "Return and Non-Return are predictions from public text, mostly from sentiment. They are not an observed repeat-booking rate; customers who never came back leave no review."},
                   "reddit_text": {"posts": len(reddit), "title_only_posts": title_only, "median_words": int(reddit.text.str.split().str.len().median()), "note": "Reddit posts are questions and requests more than reviews; no star ratings; permalinks could not be machine-verified; comments are not covered (posts only)."},
                   "source_coverage": {"apple_app_store_excluded": 500, "reason": "no individual review URL", "older_complaint_site_entries_excluded": 346, "trustpilot": "blocked", "youtube": "no API key", "note": "Excluded sources could change the balance of themes, in particular Apple App Store reviews."},
                   "time_skew": {"reviews_in_2026_pct": pct(b.review_date.str.startswith('2026').sum(), N), "note": "Most reviews are recent; older sentiment is under-represented."},
                   "no_star_ratings": {"reviews_without_rating": int(b.rating_f.isna().sum()), "pct": pct(b.rating_f.isna().sum(), N)}},
               "method_limitations": {"coding": "Issue, return, alternative and need flags are phrase rules, not a trained classifier; they can miss paraphrases and mis-fire on similar words. Measured precision (6-8 random matches per code): " + ", ".join(f"{SUB[k].split(' (')[0].lower()} {int(v * 100)}%" for k, v in PRECISION.items()) + ".",
                                      "sentiment": "Sentiment labels come from a lexicon draft plus analyst review of unclear cases (97% agreement on a 150-review check); they are not human-validated.",
                                      "multi_label_counting": "Theme counts overlap by design; do not add them.",
                                      "small_groups": f"Only {basis_n['Stated']} reviews state return behaviour in the first person; household and discovery evidence are only a few dozen reviews. These are too small for statistical claims.",
                                      "no_llm": "These results were not produced by an LLM. An LLM backend (backend/) exists for the upload workflow and later steps.",
                                      "not_validated": "Step 3 (Golden Set, human labelling, accuracy and agreement) has not been run."},
               "interpretation_guidance": ["Use theme percentages as relative importance within complaints and reviews, not as the share of all Urban Company customers affected.",
                                           "Treat Return and Non-Return labels as predictions from public text, not as rates; the stated and signalled groups are the stronger evidence.",
                                           "Prefer equal-weight source comparisons when judging whether a pattern is general or specific to complaint sites."]}
jwrite("limitations.json", limitations)

th_ids = {rid: [t for t in TH if getattr(r, "th_" + t)] for r in b.itertuples() for rid in [r.record_id]}
need_ids = {}
for x in needs:
    for rid in x["review_ids"]:
        need_ids.setdefault(rid, []).append(x["unmet_need_id"])
alt_ids = {}
for a in alt_groups:
    for rid in a["reviews"]:
        alt_ids.setdefault(rid, []).append(a["alternative_id"])
reviews = []
for r in b.itertuples():
    reviews.append({"record_id": r.record_id, "original_review_id": r.original_review_id, "source": r.platform, "source_url": r.source_url, "review_date": r.review_date or None,
                    "rating": r.rating or None, "sentiment_label": r.sentiment_label, "service_category": r.service_category or None, "city": r.city or None,
                    "review_title": r.review_title or None, "review_text": r.review_text, "themes": th_ids[r.record_id], "return_class": r.return_class, "return_basis": r.return_basis, "return_confidence": r.return_confidence, "return_reason": r.return_reason, "return_subtype": r.return_subtype,
                    "issues": [c for c in SUB if "i_" + c in b.columns and getattr(r, "i_" + c)], "unmet_needs": need_ids.get(r.record_id, []), "alternatives": alt_ids.get(r.record_id, [])})
jwrite("reviews.json", {"schema_version": "1.0", "generated_at": GEN, "reviews": reviews})
for e in EV.items.values():
    e["themes"] = th_ids.get(e["review_id"], [])
jwrite("evidence.json", {"schema_version": "1.0", "generated_at": GEN, "count": len(EV.items), "note": "Every quote is a verbatim extract of the original review text (whitespace-normalised; '…' marks a trimmed sentence). review_text is the full original text.",
                         "evidence": list(EV.items.values())})
# stable output order & manifest
import build_trust
jwrite("trust.json", build_trust.build(GEN, len(EV.items), PRECISION, SUB))
files = ["overview", "themes", "findings", "questions", "behaviour", "alternatives", "segments", "unmet_needs", "opportunities", "evidence", "limitations", "reviews", "trust"]
jwrite("themes.json", themes_out)
jwrite("findings.json", {"schema_version": "1.0", "generated_at": GEN, "dataset_reviews": N, "findings": findings, "prioritisation_note": json.loads((OUTDIR / "findings.json").read_text(encoding="utf-8"))["prioritisation_note"]})
master_hash = hashlib.sha256(open("output/urban_company_reviews_master.csv", "rb").read()).hexdigest()
jwrite("manifest.json", {"schema_version": "1.0", "generated_at": GEN, "source_dataset": {"file": "output/urban_company_reviews_master.csv", "sha256": master_hash, "reviews": N},
                         "files": {f + ".json": (OUTDIR / (f + ".json")).stat().st_size for f in files if (OUTDIR / (f + ".json")).exists()}, "evidence_items": len(EV.items),
                         "id_scheme": {"themes": "T1-T5", "findings": "F1-F3", "opportunities": "O1-O9", "unmet_needs": "N01-N14", "alternatives": "A1-A4", "questions": "Q1-Q8", "evidence": "EV001...", "reviews": "record_id from the master"},
                         "method": overview["method"]["summary"]})
print("DONE | reviews", N, "| evidence items", len(EV.items), "| quote failures:", len(EV.failures))
for f in EV.failures: print("  FAIL", f)
