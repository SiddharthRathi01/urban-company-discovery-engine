"""CSV upload validation. Pure functions: no file or network access, so they are easy to test.

File-level problems (wrong type, bad encoding, no review-text column, no usable rows) reject the whole upload with a list of errors.
Row-level problems are reported per line: rows without usable review text, malformed rows, and duplicates are rejected; bad optional
values (rating, date, URL) are dropped with a warning and the row is kept.
"""
import csv
import io
import re
from collections import Counter
from datetime import datetime

from .. import settings

CANONICAL = ["review_text", "review_id", "review_title", "platform", "source_url", "review_date", "rating", "reviewer", "service_category", "city"]
ALIASES = {
    "review_text": ["review_text", "text", "review", "content", "body", "comment", "comments", "review_body", "feedback"],
    "review_id": ["review_id", "id", "original_review_id", "record_id"],
    "review_title": ["review_title", "title", "headline", "subject"],
    "platform": ["platform", "source", "site", "channel"],
    "source_url": ["source_url", "url", "link", "review_url", "permalink"],
    "review_date": ["review_date", "date", "created_at", "posted_at", "posted", "posted_on", "timestamp", "published"],
    "rating": ["rating", "stars", "star_rating", "score"],
    "reviewer": ["reviewer", "author", "user", "username", "name", "reviewer_name"],
    "service_category": ["service_category", "category", "service"],
    "city": ["city", "location"],
}
ALLOWED_CONTENT_TYPES = {None, "", "text/csv", "application/csv", "application/vnd.ms-excel", "text/plain", "application/octet-stream", "text/x-csv"}
DATE_FORMATS = ["%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%d %b %Y", "%b %d, %Y"]
CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


class UploadRejected(Exception):
    """The whole file is unusable. .errors is a list of {code, message, ...}; .status is the HTTP status to return."""

    def __init__(self, errors, status=422):
        super().__init__(errors[0]["message"] if errors else "Upload rejected")
        self.errors, self.status = errors, status


def err(code, message, **extra):
    return {"code": code, "message": message, **extra}


def norm_header(h):
    return re.sub(r"[^a-z0-9]+", "_", (h or "").strip().lower()).strip("_")


def norm_text(s):
    return re.sub(r"\s+", " ", (s or "")).strip().lower()


def parse_date(v):
    v = (v or "").strip()
    if not v:
        return ""
    for f in DATE_FORMATS:
        try:
            return datetime.strptime(v, f).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def validate_file_meta(filename, content_type, size):
    errors = []
    if not filename or not filename.lower().endswith(".csv"):
        errors.append(err("unsupported_file_type", "Only .csv files are accepted.", filename=filename))
    ct = (content_type or "").split(";")[0].strip().lower()
    if ct not in ALLOWED_CONTENT_TYPES:
        errors.append(err("unsupported_content_type", f"Content type '{ct}' is not accepted for CSV uploads.", content_type=ct))
    if size == 0:
        errors.append(err("empty_file", "The file is empty."))
    if errors:
        raise UploadRejected(errors, 415 if errors[0]["code"].startswith("unsupported") else 422)


def decode(raw):
    if b"\x00" in raw[:4096]:
        raise UploadRejected([err("not_text_csv", "The file looks binary, not a text CSV.")])
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise UploadRejected([err("invalid_encoding", "The file is not valid UTF-8. Re-save it as 'CSV UTF-8'.", position=exc.start)])


def detect_delimiter(text):
    sample = text[:8192]
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        return ","


def map_columns(header):
    names = [norm_header(h) for h in header]
    dupes = [n for n, c in Counter(names).items() if n and c > 1]
    if dupes:
        raise UploadRejected([err("duplicate_columns", "Column names must be unique.", columns=dupes)])
    mapping, used = {}, set()
    for canon in CANONICAL:
        for alias in ALIASES[canon]:
            if alias in names and alias not in used:
                mapping[canon] = names.index(alias); used.add(alias)
                break
    if "review_text" not in mapping:
        raise UploadRejected([err("missing_required_column", "No review text column found.", required="review_text", accepted_names=ALIASES["review_text"], found_columns=[h for h in header if h.strip()])])
    ignored = [header[i] for i, n in enumerate(names) if n not in used]
    return mapping, ignored


def validate(raw, filename, content_type, approved_texts=frozenset()):
    """Return a report dict: {summary, column_mapping, ignored_columns, issue_counts, issues, accepted_rows}. Raises UploadRejected for file-level errors."""
    validate_file_meta(filename, content_type, len(raw))
    text = decode(raw)
    delim = detect_delimiter(text)
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delim)
    try:
        header = next((r for r in reader if any(c.strip() for c in r)), None)
        if header is None:
            raise UploadRejected([err("empty_file", "The file has no header row.")])
        mapping, ignored = map_columns(header)
        issues, counts = [], Counter()
        accepted, seen_text, seen_id = [], {}, {}
        total = 0

        def add_issue(line, severity, code, message, field=None):
            counts[code] += 1
            if len(issues) < settings.MAX_ISSUES_STORED:
                issues.append({"line": line, "severity": severity, "code": code, "message": message, "field": field})

        for row in reader:
            line = reader.line_num
            if not any(c.strip() for c in row):
                continue
            total += 1
            if total > settings.MAX_UPLOAD_ROWS:
                raise UploadRejected([err("too_many_rows", f"The file has more than {settings.MAX_UPLOAD_ROWS} rows.", limit=settings.MAX_UPLOAD_ROWS)], 413)
            if len(row) != len(header):
                add_issue(line, "error", "column_count_mismatch", f"Row has {len(row)} fields but the header has {len(header)}.")
                continue
            get = lambda k: row[mapping[k]].strip() if k in mapping else ""
            body = get("review_text")
            if not body:
                add_issue(line, "error", "missing_review_text", "Review text is empty.", "review_text"); continue
            if CONTROL.search(body):
                body = CONTROL.sub(" ", body)
            if len(body) < settings.MIN_REVIEW_CHARS:
                add_issue(line, "error", "review_text_too_short", f"Review text is shorter than {settings.MIN_REVIEW_CHARS} characters.", "review_text"); continue
            if len(body) > settings.MAX_REVIEW_CHARS:
                add_issue(line, "error", "review_text_too_long", f"Review text is longer than {settings.MAX_REVIEW_CHARS} characters.", "review_text"); continue
            rid = get("review_id")
            if rid and rid in seen_id:
                add_issue(line, "error", "duplicate_review_id", f"Review id '{rid}' already appears on line {seen_id[rid]}.", "review_id"); continue
            title, platform = get("review_title"), get("platform")
            key = (norm_text(body), platform.lower())
            if key in seen_text:
                add_issue(line, "error", "duplicate_in_file", f"Same review text and source as line {seen_text[key]}.", "review_text"); continue
            if norm_text(body) in approved_texts or norm_text(title + " " + body) in approved_texts:
                add_issue(line, "error", "already_in_approved_dataset", "This review text is already in the approved Urban Company dataset.", "review_text"); continue
            rating = get("rating")
            if rating:
                try:
                    r = float(rating)
                    if not 1 <= r <= 5:
                        raise ValueError
                    rating = str(int(r)) if r == int(r) else str(r)
                except ValueError:
                    add_issue(line, "warning", "invalid_rating", f"Rating '{rating}' is not a number from 1 to 5; value dropped.", "rating"); rating = ""
            date = parse_date(get("review_date"))
            if date is None:
                add_issue(line, "warning", "invalid_date", f"Date '{get('review_date')}' was not recognised; value dropped.", "review_date"); date = ""
            url = get("source_url")
            if url and not re.match(r"^https?://\S+$", url):
                add_issue(line, "warning", "invalid_url", "Source URL must start with http:// or https://; value dropped.", "source_url"); url = ""
            if rid:
                seen_id[rid] = line
            seen_text[key] = line
            accepted.append({"row_id": f"ROW-{len(accepted) + 1:05d}", "source_line": line, "review_id": rid, "review_title": title, "review_text": body, "platform": platform, "source_url": url,
                             "review_date": date, "rating": rating, "reviewer": get("reviewer"), "service_category": get("service_category"), "city": get("city")})
    except csv.Error as exc:
        raise UploadRejected([err("malformed_csv", f"The CSV could not be parsed: {exc}")])
    if not accepted:
        raise UploadRejected([err("no_valid_rows", "No row passed validation.", rows_checked=total, issue_counts=dict(counts), issues=issues[:20])])
    n_err = sum(c for k, c in counts.items() if k not in ("invalid_rating", "invalid_date", "invalid_url"))
    return {"summary": {"rows_in_file": total, "accepted": len(accepted), "rejected": n_err, "malformed": counts["column_count_mismatch"],
                        "duplicates_in_file": counts["duplicate_in_file"] + counts["duplicate_review_id"], "already_in_approved_dataset": counts["already_in_approved_dataset"],
                        "rows_with_warnings": sum(1 for i in issues if i["severity"] == "warning"), "delimiter": delim},
            "column_mapping": {k: header[v] for k, v in mapping.items()}, "ignored_columns": ignored, "issue_counts": dict(counts), "issues": issues,
            "issues_truncated": sum(counts.values()) > len(issues), "accepted_rows": accepted}
