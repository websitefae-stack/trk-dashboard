"""
Seeds the "Podcast Guest Form Invite" Email Template (see
email_templates.render_email/PODCAST_INVITE_TEMPLATE), same self-healing
approach as create_dashboard_email_templates.py - a standalone patch
rather than adding to that one, since it's already run on this site and
won't fire again to pick up a new entry.

Used by leads.send_intake_form when the lead's appointment_type is a
podcast booking (see is_podcast_lead) - sends the Podcast Guest Booking
Form link instead of the usual client intake form.
"""

import frappe

from dashboard.api.shared.email_templates import PODCAST_INVITE_TEMPLATE

BODY_FIELD_CANDIDATES = ["response", "response_html", "message", "content"]

SUBJECT = "Your Resilient Kid Podcast guest form"
BODY = (
    "Hi {{ contact_name }},\n"
    "\n"
    "Thanks for your interest in joining The Resilient Kid Podcast! Please complete "
    "the short form below so we can start planning your episode:\n"
    "\n"
    "{{ intake_url }}"
)


def _body_fieldname(meta):
    for fieldname in BODY_FIELD_CANDIDATES:
        if meta.has_field(fieldname):
            return fieldname
    return None


def _is_blank(value):
    return not (value or "").strip()


def execute():
    if not frappe.db.exists("DocType", "Email Template"):
        return

    meta = frappe.get_meta("Email Template")
    body_fieldname = _body_fieldname(meta)

    if not body_fieldname:
        frappe.log_error(
            f"Email Template has none of the expected body fields {BODY_FIELD_CANDIDATES}. "
            f"Actual fields: {[f.fieldname for f in meta.fields]}",
            "Create Podcast Invite Email Template - No Body Field Found",
        )
        return

    try:
        if frappe.db.exists("Email Template", PODCAST_INVITE_TEMPLATE):
            doc = frappe.get_doc("Email Template", PODCAST_INVITE_TEMPLATE)

            if not _is_blank(doc.get("subject")) or not _is_blank(doc.get(body_fieldname)):
                return

            if meta.has_field("subject"):
                doc.subject = SUBJECT

            doc.set(body_fieldname, BODY)
            doc.save(ignore_permissions=True)
        else:
            doc = frappe.new_doc("Email Template")
            doc.name = PODCAST_INVITE_TEMPLATE

            if meta.has_field("subject"):
                doc.subject = SUBJECT

            doc.set(body_fieldname, BODY)
            doc.insert(ignore_permissions=True)
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Create Podcast Invite Email Template Failed: {PODCAST_INVITE_TEMPLATE}")

    frappe.db.commit()
