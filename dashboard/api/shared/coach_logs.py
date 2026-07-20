"""
"Coach Logs" report tab: each coach's own Mileage Log and Training And
Supervision Log entries - self-logged records that aren't tied to any
client, unlike every other report/form in this app. A coach only ever
sees/adds their own entries; a franchisor/office login can pick a coach
from a dropdown (or leave it unset to see everyone's) but never adds an
entry unless they also have their own Coach profile.
"""

import frappe
from frappe import _
from frappe.utils import flt

from dashboard.api.shared.permissions import (
    ensure_logged_in,
    is_franchisor_user,
    get_current_coach_name,
)
from dashboard.api.shared.clients import get_coach_label
from dashboard.api.shared.invoices import _get_coach_options


def _coach_filter(coach=None):
    """
    None means "no filter" (franchisor left the coach picker on "All
    Coaches"). Otherwise a specific coach name to filter by - trusted from
    the request only when the caller is a franchisor; a coach's own login
    always gets forced to their own coach name regardless of what's
    passed, the same "never trust the client for this decision" approach
    used by _lead_filters_for_forms_report() in form_reports.py.
    """
    ensure_logged_in()

    if is_franchisor_user():
        coach = (coach or "").strip()
        return coach or None

    coach_name = get_current_coach_name(optional=True)
    return coach_name or "__none__"


@frappe.whitelist()
def get_coach_log_options():
    """
    Coach dropdown for the Coach Logs tab - populated only for
    franchisor/office logins (a coach never needs to pick, they only ever
    see their own). An empty list is also the JS's signal to hide the
    dropdown entirely.
    """
    ensure_logged_in()

    if not is_franchisor_user():
        return []

    return _get_coach_options()


@frappe.whitelist()
def add_mileage_log(log_date=None, purpose=None, miles=None, notes=None):
    ensure_logged_in()

    coach_name = get_current_coach_name(optional=True)
    if not coach_name:
        frappe.throw(_("Only coaches can log mileage."))

    purpose = (purpose or "").strip()
    if not purpose:
        frappe.throw(_("Purpose / journey is required."))

    miles = flt(miles, 1)
    if miles <= 0:
        frappe.throw(_("Miles must be greater than zero."))

    doc = frappe.new_doc("Mileage Log")
    doc.coach = coach_name
    doc.log_date = log_date or frappe.utils.nowdate()
    doc.purpose = purpose
    doc.miles = miles
    doc.notes = (notes or "").strip()
    doc.insert(ignore_permissions=True)
    frappe.db.commit()

    return {"ok": 1}


@frappe.whitelist()
def get_mileage_log(coach=None, from_date=None, to_date=None):
    coach_filter = _coach_filter(coach)

    if coach_filter == "__none__":
        return []

    filters = {}
    if coach_filter:
        filters["coach"] = coach_filter

    if from_date or to_date:
        filters["log_date"] = [
            "between",
            [from_date or "1970-01-01", to_date or frappe.utils.nowdate()],
        ]

    rows = frappe.get_all(
        "Mileage Log",
        filters=filters,
        fields=["name", "coach", "log_date", "purpose", "miles", "notes"],
        order_by="log_date desc, creation desc",
        limit_page_length=2000,
        ignore_permissions=True,
    )

    for row in rows:
        row["coach_label"] = get_coach_label(row.get("coach"))

    return rows


@frappe.whitelist()
def add_training_log(log_date=None, log_type=None, description=None, duration_hours=None):
    ensure_logged_in()

    coach_name = get_current_coach_name(optional=True)
    if not coach_name:
        frappe.throw(_("Only coaches can log training or supervision."))

    log_type = (log_type or "").strip()
    if log_type not in ("Training", "Supervision"):
        frappe.throw(_("Select whether this is Training or Supervision."))

    description = (description or "").strip()
    if not description:
        frappe.throw(_("Description is required."))

    doc = frappe.new_doc("Training And Supervision Log")
    doc.coach = coach_name
    doc.log_date = log_date or frappe.utils.nowdate()
    doc.log_type = log_type
    doc.description = description
    doc.duration_hours = flt(duration_hours, 1) if duration_hours else None
    doc.insert(ignore_permissions=True)
    frappe.db.commit()

    return {"ok": 1}


@frappe.whitelist()
def get_training_log(coach=None, from_date=None, to_date=None):
    coach_filter = _coach_filter(coach)

    if coach_filter == "__none__":
        return []

    filters = {}
    if coach_filter:
        filters["coach"] = coach_filter

    if from_date or to_date:
        filters["log_date"] = [
            "between",
            [from_date or "1970-01-01", to_date or frappe.utils.nowdate()],
        ]

    rows = frappe.get_all(
        "Training And Supervision Log",
        filters=filters,
        fields=["name", "coach", "log_date", "log_type", "description", "duration_hours"],
        order_by="log_date desc, creation desc",
        limit_page_length=2000,
        ignore_permissions=True,
    )

    for row in rows:
        row["coach_label"] = get_coach_label(row.get("coach"))

    return rows
