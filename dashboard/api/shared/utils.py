"""
Shared low-level helpers used across multiple API modules.
"""
import datetime

import frappe
from frappe import _
from frappe.utils import get_fullname


def get_label(row, fields):
    if not row:
        return ""

    for fieldname in fields:
        value = (row.get(fieldname) or "").strip()
        if value:
            return value

    return row.get("name") or ""


def get_request_payload():
    try:
        if getattr(frappe, "request", None):
            payload = frappe.request.get_json(silent=True) or {}
            if isinstance(payload, dict):
                return payload
    except Exception:
        pass
    return {}


def coalesce_raw(fieldname, explicit_value=None):
    if explicit_value not in (None, ""):
        return explicit_value

    payload = get_request_payload()
    if fieldname in payload and payload.get(fieldname) not in (None, ""):
        return payload.get(fieldname)

    form_value = frappe.form_dict.get(fieldname)
    if form_value not in (None, ""):
        return form_value

    return explicit_value


def coalesce_str(fieldname, explicit_value=None):
    value = coalesce_raw(fieldname, explicit_value)
    return (value or "").strip() if isinstance(value, str) else (str(value).strip() if value not in (None, "") else "")


def parse_date_input(value):
    """
    A date typed/picked in the browser arrives here as whatever that
    particular input actually submitted - normally ISO (a native
    <input type="date"> field always produces yyyy-mm-dd), but a value
    ever round-tripped through a non-native date field, or re-saved from
    a prefilled value already stored/displayed in this site's UK
    dd/mm/yyyy format, comes back in that format instead - and MySQL's
    DATE column rejects anything that isn't yyyy-mm-dd outright,
    crashing the whole save with a raw SQL error (1292) instead of a
    normal validation message. Tries ISO first, then UK dd/mm/yyyy, and
    only throws a clear, catchable error if neither parses -
    deliberately not using a generic/dateutil-style parser here, since
    "11/08/2026" is genuinely ambiguous (11th Aug vs Nov 8th) and a
    silent wrong-format guess would corrupt the date rather than fail
    loudly. Returns None for a blank value - "no date set" is valid.
    """
    value = (value or "").strip()
    if not value:
        return None

    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.datetime.strptime(value, fmt).date()
        except ValueError:
            continue

    frappe.throw(_("'{0}' isn't a valid date - use dd/mm/yyyy.").format(value))


_SW_LABEL_FIELDS = ["sw_name", "session_worker_name", "full_name", "employee_name", "user_full_name", "title"]
_SW_LOGIN_FIELDS = ["user", "user_id", "email", "session_worker_email"]


def find_session_worker_for_user(user, fullname=None):
    if not frappe.db.exists("DocType", "Session Worker"):
        return None

    if fullname is None:
        fullname = (get_fullname(user) or "").strip()

    meta = frappe.get_meta("Session Worker")
    fields = ["name"]
    for f in _SW_LABEL_FIELDS + _SW_LOGIN_FIELDS:
        if meta.has_field(f) and f not in fields:
            fields.append(f)

    for login_field in _SW_LOGIN_FIELDS:
        if meta.has_field(login_field):
            row = frappe.db.get_value("Session Worker", {login_field: user}, fields, as_dict=True)
            if row:
                return {
                    "doctype": "Session Worker",
                    "name": row.get("name"),
                    "label": get_label(row, _SW_LABEL_FIELDS + ["name"]),
                }

    for label_field in _SW_LABEL_FIELDS:
        if fullname and meta.has_field(label_field):
            row = frappe.db.get_value("Session Worker", {label_field: fullname}, fields, as_dict=True)
            if row:
                return {
                    "doctype": "Session Worker",
                    "name": row.get("name"),
                    "label": get_label(row, _SW_LABEL_FIELDS + ["name"]),
                }

    return None
