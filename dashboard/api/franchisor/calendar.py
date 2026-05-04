import frappe
from frappe import _
from frappe.utils import add_to_date, getdate, get_datetime, get_fullname

from dashboard.api.session_worker import calendar as sw_calendar


FRANCHISOR_ME_VALUE = "__franchisor_me__"
COACH_PREFIX = "coach::"
SESSION_WORKER_PREFIX = "session_worker::"


def _require_logged_in_user():
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)


def _get_current_franchisor_context(user):
    fullname = (get_fullname(user) or "").strip()

    return {
        "user": user,
        "franchisor_name": user,
        "franchisor_label": fullname or user,
        "resolution_note": "Franchisor calendar access.",
        "is_dashboard_admin": 1,
    }


def _get_label(row, fields):
    for fieldname in fields:
        value = (row.get(fieldname) or "").strip()
        if value:
            return value
    return row.get("name") or ""


def _get_client_base_fields():
    if not frappe.db.exists("DocType", "Client"):
        return []

    meta = frappe.get_meta("Client")
    fields = ["name"]

    for fieldname in [
        "session_worker",
        "primary_coach",
        "attending_coach",
        "full_name",
        "name1",
        "last_name",
        "preferred_name",
        "travel_charged",
        "travel_miles_one_way",
    ]:
        if meta.has_field(fieldname) and fieldname not in fields:
            fields.append(fieldname)

    return fields


def _get_client_row(client):
    if not client or not frappe.db.exists("Client", client):
        return None

    return frappe.db.get_value("Client", client, _get_client_base_fields(), as_dict=True)


def _get_client_display_from_row(row):
    if not row:
        return ""

    for fieldname in ["full_name", "preferred_name", "name1", "name"]:
        value = (row.get(fieldname) or "").strip()
        if value:
            return value

    first = (row.get("name1") or "").strip()
    last = (row.get("last_name") or "").strip()
    return " ".join([part for part in [first, last] if part]).strip() or row.get("name")


def _get_coach_label(coach):
    if not coach:
        return ""

    if not frappe.db.exists("DocType", "Coach"):
        return coach

    meta = frappe.get_meta("Coach")
    label_fields = ["coach_name", "full_name", "employee_name", "user_full_name", "title", "name"]

    fields = ["name"]
    for fieldname in label_fields:
        if meta.has_field(fieldname) and fieldname not in fields:
            fields.append(fieldname)

    row = frappe.db.get_value
