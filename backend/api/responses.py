"""Consistent response envelope, pagination and error type.

Success : {"data": <object | list>, "meta": {...}}      list endpoints add meta.page/page_size/total/total_pages
Error   : {"error": {"code": str, "message": str, "details": any}}
"""
import math

from . import settings


class ApiError(Exception):
    def __init__(self, status, code, message, details=None):
        super().__init__(message)
        self.status, self.code, self.message, self.details = status, code, message, details


def not_found(kind, ident):
    return ApiError(404, f"{kind}_not_found", f"No {kind.replace('_', ' ')} with id '{ident}'.", {"id": ident})


def bad_filter(name, value, allowed=None):
    d = {"parameter": name, "value": value}
    if allowed is not None:
        d["allowed"] = sorted(allowed)
    return ApiError(422, "invalid_filter", f"Invalid value for '{name}'.", d)


def envelope(data, meta=None):
    return {"data": data, "meta": meta or {}}


def paginate(items, page, page_size, meta=None):
    total = len(items)
    pages = max(1, math.ceil(total / page_size)) if total else 0
    if total and page > pages:
        raise ApiError(404, "page_out_of_range", f"Page {page} is beyond the last page ({pages}).", {"page": page, "total_pages": pages})
    start = (page - 1) * page_size
    m = dict(meta or {})
    m.update({"page": page, "page_size": page_size, "total": total, "total_pages": pages})
    return envelope(items[start:start + page_size], m)


def clamp_page_size(n):
    return max(1, min(n, settings.MAX_PAGE_SIZE))


def csv_list(value):
    """'a,b' or None -> ['a','b'] / None."""
    if value is None:
        return None
    out = [v.strip() for v in value.split(",") if v.strip()]
    return out or None
