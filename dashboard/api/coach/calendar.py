import frappe
from frappe import _
from frappe.utils import add_to_date, getdate, get_datetime, get_fullname

from dashboard.api.session_worker import calendar as sw_calendar


COACH_ME_VALUE = "__coach_me__"

DASHBOARD_ADMIN_USERS = [
    "hq@theresilientkid.co.uk",
    "office@theresilientpeople.uk",
]


def _require_logged_in_user():
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)


def _is_dashboard_admin():
    return (frappe.session.user or "").strip().lower() in {email.lower() for email in DASHBOARD_ADMIN_USERS}


def _get_current_coach_context(user):
    fullname = (get_fullname(user) or "").strip()

    context = {
        "user": user,
        "coach_name": None,
        "coach_label": fullname or user,
        "resolution_note": "",
        "is_dashboard_admin": _is_dashboard_admin(),
    }

    if context["is_dashboard_admin"]:
        context["coach_label"] = "Dashboard Admin"
        context["resolution_note"] = "Dashboard admin access."
        return context

    if not frappe.db.exists("DocType", "Coach"):
        context["resolution_note"] = "Could not find Coach DocType."
        return context

    meta = frappe.get_meta("Coach")
    fields = ["name"]

    label_fields = ["coach_name", "full_name", "employee_name", "user_full_name", "title", "name"]
    login_fields = ["user", "user_id", "email", "coach_email"]

    for fieldname in label_fields + login_fields:
        if meta.has_field(fieldname) and fieldname not in fields:
            fields.append(fieldname)

    for login_field in login_fields:
        if meta.has_field(login_field):
            row = frappe.db.get_value("Coach", {login_field: user}, fields, as_dict=True)
            if row:
                context["coach_name"] = row.get("name")
                context["coach_label"] = _get_label(row, label_fields)
                context["resolution_note"] = "Resolved logged-in user to Coach / " + row.get("name")
                return context

    for label_field in label_fields:
        if fullname and meta.has_field(label_field):
            row = frappe.db.get_value("Coach", {label_field: fullname}, fields, as_dict=True)
            if row:
                context["coach_name"] = row.get("name")
                context["coach_label"] = _get_label(row, label_fields)
                context["resolution_note"] = "Resolved logged-in user to Coach / " + row.get("name")
                return context

    context["resolution_note"] = "Could not resolve the logged-in user to a Coach record."
    return context


def _get_label(row, fields):
    for fieldname in fields:
        value = (row.get(fieldname) or "").strip()
        if value:
            return value
    return row.get("name") or ""


def _coach_can_view_client(client_row, coach_context):
    if coach_context.get("is_dashboard_admin"):
        return True

    coach_name = (coach_context.get("coach_name") or "").strip()
    if not coach_name:
        return False

    return client_row.get("primary_coach") == coach_name or client_row.get("attending_coach") == coach_name


def _get_client_base_fields():
    if not frappe.db.exists("DocType", "Client"):
        return []

    meta = frappe.get_meta("Client")
    fields = ["name"]

    for
