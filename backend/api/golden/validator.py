"""Validation of a golden-set CSV: review text plus the human labels (sentiment and/or Return / Non-Return, optional problem label)."""
import csv
import io
import re
from collections import Counter

from .. import settings
from ..uploads.validator import UploadRejected, decode, detect_delimiter, err, norm_header, norm_text, validate_file_meta

FIELDS = ["text", "id", "human_sentiment", "human_return", "human_theme", "rating", "source_url", "source"]
ALIASES = {
    "text": ["review_text", "text", "review", "comment", "comments", "content", "body", "feedback"],
    "id": ["review_id", "id", "record_id", "comment_id"],
    "human_sentiment": ["human_sentiment", "your_sentiment", "sentiment", "mood", "human_mood", "label_sentiment"],
    "human_return": ["human_return", "your_return", "return_label", "return_class", "return_call", "return_decision", "return_prediction", "return", "human_return_label", "will_return", "repeat"],
    "human_theme": ["human_theme", "your_label", "human_label", "your_problem_label", "problem_label", "problem", "main_problem", "theme", "label", "issue"],
    "rating": ["rating", "stars", "star_rating", "score"],
    "source_url": ["source_url", "url", "link", "review_url", "permalink"],
    "source": ["platform", "source", "site", "channel"],
}
SENT = {"positive": "Positive", "pos": "Positive", "p": "Positive", "happy": "Positive", "good": "Positive", "negative": "Negative", "neg": "Negative", "n": "Negative", "unhappy": "Negative", "bad": "Negative",
        "neutral": "Neutral", "neu": "Neutral", "mixed": "Mixed", "mix": "Mixed", "m": "Mixed"}
RET = {"return": "Return", "returns": "Return", "will return": "Return", "likely to return": "Return", "repeat": "Return", "yes": "Return", "r": "Return", "y": "Return",
       "non-return": "Non-Return", "nonreturn": "Non-Return", "non return": "Non-Return", "will not return": "Non-Return", "wont return": "Non-Return", "won't return": "Non-Return", "no": "Non-Return",
       "churn": "Non-Return", "not return": "Non-Return", "nr": "Non-Return", "n/r": "Non-Return", "leave": "Non-Return",
       "insufficient": "Insufficient Evidence", "insufficient evidence": "Insufficient Evidence", "unclear": "Insufficient Evidence", "unknown": "Insufficient Evidence", "na": "Insufficient Evidence",
       "n/a": "Insufficient Evidence", "cant say": "Insufficient Evidence", "can't say": "Insufficient Evidence", "neutral": "Insufficient Evidence", "i": "Insufficient Evidence"}


def propose_mapping(header):
    names = [norm_header(h) for h in header]
    out = {}
    for f in FIELDS:
        for a in ALIASES[f]:
            if a in names and header[names.index(a)] not in out.values():
                out[f] = header[names.index(a)]
                break
    return out


def validate_golden(raw, filename, content_type, mapping=None):
    """Returns {summary, column_mapping, issues, rows}. Raises UploadRejected for file-level problems."""
    validate_file_meta(filename, content_type, len(raw))
    text = decode(raw)
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=detect_delimiter(text))
    header = next((r for r in reader if any(c.strip() for c in r)), None)
    if header is None:
        raise UploadRejected([err("empty_file", "The file has no header row.")])
    if len({norm_header(h) for h in header if h.strip()}) != len([h for h in header if h.strip()]):
        raise UploadRejected([err("duplicate_columns", "Column names must be unique.")])
    cols = {h: i for i, h in enumerate(header)}
    m = {k: v for k, v in (mapping or {}).items() if v}
    bad = [v for v in m.values() if v not in cols]
    if bad:
        raise UploadRejected([err("unknown_column", "The mapping names columns that are not in the file.", columns=bad, found_columns=header)])
    mp = {**propose_mapping(header), **m} if not mapping else m
    if "text" not in mp:
        raise UploadRejected([err("missing_required_column", "No review text column found.", required="text", accepted_names=ALIASES["text"], found_columns=header)])
    if "human_sentiment" not in mp and "human_return" not in mp:
        raise UploadRejected([err("missing_human_labels", "A golden set needs your own labels: at least a sentiment column or a Return / Non-Return column.", accepted_sentiment=ALIASES["human_sentiment"],
                                  accepted_return=ALIASES["human_return"], found_columns=header)])
    issues, counts, rows, seen = [], Counter(), [], {}
    total = 0

    def issue(line, sev, code, msg):
        counts[code] += 1
        if len(issues) < settings.MAX_ISSUES_STORED:
            issues.append({"line": line, "severity": sev, "code": code, "message": msg})

    for row in reader:
        line = reader.line_num
        if not any(c.strip() for c in row):
            continue
        total += 1
        if total > settings.MAX_GOLDEN_ROWS:
            raise UploadRejected([err("too_many_rows", f"A golden set can have at most {settings.MAX_GOLDEN_ROWS} rows (each is analysed by the AI).", limit=settings.MAX_GOLDEN_ROWS)], 413)
        if len(row) != len(header):
            issue(line, "error", "column_count_mismatch", f"Row has {len(row)} fields but the header has {len(header)}."); continue
        get = lambda k: row[cols[mp[k]]].strip() if k in mp else ""
        body = get("text")
        if not body:
            issue(line, "error", "missing_review_text", "Review text is empty."); continue
        key = norm_text(body)
        if key in seen:
            issue(line, "error", "duplicate_in_file", f"Same review text as line {seen[key]}."); continue
        hs, hr = get("human_sentiment"), get("human_return")
        sent = SENT.get(hs.lower()) if hs else None
        ret = RET.get(hr.lower().strip()) if hr else None
        if hs and sent is None:
            issue(line, "warning", "unrecognised_sentiment", f"Sentiment '{hs}' is not Positive, Negative, Neutral or Mixed; ignored for this row.")
        if hr and ret is None:
            issue(line, "warning", "unrecognised_return_label", f"Return label '{hr}' is not Return, Non-Return or Insufficient Evidence; ignored for this row.")
        if sent is None and ret is None:
            issue(line, "error", "no_usable_human_label", "This row has no usable human label."); continue
        rt = get("rating")
        try:
            rt = str(float(rt)).rstrip("0").rstrip(".") if rt else ""
        except ValueError:
            issue(line, "warning", "invalid_rating", f"Rating '{rt}' is not a number; ignored."); rt = ""
        seen[key] = line
        rows.append({"row_id": f"ROW-{len(rows) + 1:05d}", "review_id": get("id") or f"G-{len(rows) + 1:04d}", "review_text": body, "human_sentiment": sent, "human_return": ret,
                     "human_theme": get("human_theme") or None, "rating": rt, "source_url": get("source_url") or "", "source": get("source") or "", "source_line": line})
    if not rows:
        raise UploadRejected([err("no_valid_rows", "No row passed validation.", rows_checked=total, issue_counts=dict(counts), issues=issues[:20])])
    return {"summary": {"rows_in_file": total, "accepted": len(rows), "rejected": sum(c for k, c in counts.items() if k in ("missing_review_text", "duplicate_in_file", "no_usable_human_label", "column_count_mismatch")),
                        "with_sentiment_label": sum(1 for r in rows if r["human_sentiment"]), "with_return_label": sum(1 for r in rows if r["human_return"]),
                        "with_problem_label": sum(1 for r in rows if r["human_theme"])},
            "column_mapping": mp, "issues": issues, "issue_counts": dict(counts), "rows": rows}
