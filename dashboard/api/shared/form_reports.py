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
from dashboard.api.shared.leads import (
    LEAD_DOCTYPE,
    ensure_lead_access,
    get_intake_question_fields,
    get_intake_field_value,
)
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
        limit_page_length=2000,
        ignore_permissions=True,
    )

    # frappe.get_all()'s order_by validation rejects raw SQL like
    # coalesce(...) (only 'field', 'link_field.field', 'child_table.field'
    # are allowed), so the "completed date, falling back to sent date" sort
    # is done here instead.
    rows.sort(key=lambda row: row.get("intake_completed_on") or row.get("intake_sent_on"), reverse=True)

    for row in rows:
        row["coach_label"] = get_coach_label(row.get("coach"))
        row["is_completed"] = 1 if row.get("intake_completed_on") else 0

    return rows


@frappe.whitelist()
def get_intake_form_questions():
    """
    Every "question" the intake form can be broken down by - powers the
    Reports section's "one question - everyone's answer" view. No access
    check beyond being logged in: this only lists field labels, never
    answer data.
    """
    ensure_logged_in()

    return [
        {"value": "client_name", "label": "Client Name"},
        {"value": "contact_name", "label": "Contact Name"},
    ] + [
        {"value": df.fieldname, "label": df.label or df.fieldname}
        for df in get_intake_question_fields()
    ]


@frappe.whitelist()
def get_intake_form_answers_for_person(name=None):
    """One lead's full set of intake answers - the "one specific person" view."""
    doc = ensure_lead_access(name)

    if not doc.get("intake_sent_on"):
        frappe.throw(_("This lead has no intake form."))

    answers = [{"label": "Client Name", "value": doc.client_name}, {"label": "Contact Name", "value": doc.contact_name}]
    answers += [
        {"label": df.label or df.fieldname, "value": get_intake_field_value(doc, df)}
        for df in get_intake_question_fields()
        if get_intake_field_value(doc, df) is not None
    ]

    return {
        "name": doc.name,
        "client_name": doc.client_name,
        "contact_name": doc.contact_name,
        "coach_label": get_coach_label(doc.coach),
        "answers": answers,
    }


@frappe.whitelist()
def get_intake_form_answers_for_question(question=None):
    """Every accessible lead's answer to one specific intake question."""
    ensure_logged_in()

    question = (question or "").strip()
    if not question:
        frappe.throw(_("Select a question."))

    label = question
    df = None

    if question in ("client_name", "contact_name"):
        label = "Client Name" if question == "client_name" else "Contact Name"
    else:
        # Only fields get_intake_form_questions() actually offered - not any
        # arbitrary Lead fieldname (e.g. the internal "status"/"coach"/
        # "source" fields _INTAKE_PDF_SKIP_FIELDS deliberately excludes from
        # "questions").
        matching = [f for f in get_intake_question_fields() if f.fieldname == question]
        if not matching:
            frappe.throw(_("Unknown question."))
        df = matching[0]
        label = df.label or question

    filters = _lead_filters_for_forms_report()
    filters = dict(filters) if filters else {}
    filters["intake_sent_on"] = ["is", "set"]

    lead_names = frappe.get_all(
        LEAD_DOCTYPE, filters=filters, pluck="name", limit_page_length=2000, ignore_permissions=True
    )

    rows = []
    for lead_name in lead_names:
        doc = frappe.get_doc(LEAD_DOCTYPE, lead_name)
        value = doc.get(question) if df is None else get_intake_field_value(doc, df)

        rows.append({
            "lead": lead_name,
            "client_name": doc.client_name,
            "coach_label": get_coach_label(doc.coach),
            "value": value or "",
        })

    return {"question": label, "rows": rows}


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
