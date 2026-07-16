"""
"Forms" report for the Reports section: Intake Forms (Client Lead's
intake questionnaire) and Feedback Forms (Client session notes logged as
"Parent Feedback"), scoped the same way every other list in this app is -
coaches see their own, franchisors see everyone's. Both are read-only
summaries that link out to the existing lead/client detail pages rather
than duplicating their full answer/notes rendering here.
"""

import frappe
from frappe import _

from dashboard.api.shared.permissions import (
    ensure_logged_in,
    is_franchisor_user,
    get_current_coach_name,
    get_allowed_client_names,
)
from dashboard.api.shared.leads import LEAD_DOCTYPE
from dashboard.api.shared.clients import get_coach_label

FEEDBACK_NOTE_DOCTYPE = "Notes"
FEEDBACK_SESSION_TYPES = ["Parent Feedback"]


def _lead_filters_for_forms_report():
    """
    None means "no filter" (franchisor sees every lead's intake form). Any
    other value restricts to the current coach's own leads.

    Deliberately does NOT accept a dashboard_type argument from the
    caller - is_franchisor_user() is derived purely from
    frappe.session.user, so a client-supplied "dashboard_type": "franchisor"
    can never widen what this returns. (leads.py's own equivalent helper
    ORs in a caller-supplied dashboard_type; not copied here on purpose,
    since intake answers include contact details and this report has no
    legitimate reason to trust anything from the request body for that
    decision.)
    """
    ensure_logged_in()

    if is_franchisor_user():
        return None

    coach_name = get_current_coach_name(optional=True)

    if not coach_name:
        return {"name": ["in", []]}

    return {"coach": coach_name}


@frappe.whitelist()
def get_intake_form_report():
    ensure_logged_in()

    filters = _lead_filters_for_forms_report()
    filters = dict(filters) if filters else {}
    filters["intake_sent_on"] = ["is", "set"]

    rows = frappe.get_all(
        LEAD_DOCTYPE,
        filters=filters,
        fields=[
            "name",
            "client_name",
            "contact_name",
            "contact_email",
            "coach",
            "client_type",
            "status",
            "intake_sent_on",
            "intake_completed_on",
        ],
        order_by="coalesce(intake_completed_on, intake_sent_on) desc",
        limit_page_length=2000,
        ignore_permissions=True,
    )

    for row in rows:
        row["coach_label"] = get_coach_label(row.get("coach"))
        row["is_completed"] = 1 if row.get("intake_completed_on") else 0

    return rows


@frappe.whitelist()
def get_feedback_form_report():
    """
    Deliberately takes no arguments - see _lead_filters_for_forms_report()
    above for why franchisor-vs-coach scope is never taken from the
    request.
    """
    ensure_logged_in()

    if is_franchisor_user():
        client_names = None
    else:
        client_names = get_allowed_client_names()

        if not client_names:
            return []

    filters = {
        "parenttype": "Client",
        "parentfield": "session_notes",
        "session_type": ["in", FEEDBACK_SESSION_TYPES],
    }

    if client_names is not None:
        filters["parent"] = ["in", client_names]

    rows = frappe.get_all(
        FEEDBACK_NOTE_DOCTYPE,
        filters=filters,
        fields=[
            "name",
            "parent as client",
            "session_date",
            "session_type",
            "notes",
            "user",
            "creation",
        ],
        order_by="session_date desc, creation desc",
        limit_page_length=2000,
        ignore_permissions=True,
    )

    for row in rows:
        row["client_label"] = _client_display_name(row.get("client"))
        row["coach_label"] = _coach_label_for_client(row.get("client"))
        row["user_label"] = (
            frappe.get_cached_value("User", row.get("user"), "full_name") if row.get("user") else ""
        ) or row.get("user") or ""

    return rows


def _client_display_name(client_name):
    if not client_name:
        return ""

    return (
        frappe.db.get_value("Client", client_name, "full_name")
        or client_name
    )


def _coach_label_for_client(client_name):
    if not client_name:
        return ""

    coach_name = frappe.db.get_value("Client", client_name, "primary_coach") or frappe.db.get_value(
        "Client", client_name, "attending_coach"
    )

    return get_coach_label(coach_name)
