"""
Seeds the "Franchise Brochure Link - Resilient Kid" Email Template
(see email_templates.FRANCHISE_BROCHURE_LINK_TEMPLATE / franchise_
brochure.send_brochure_link) - same self-healing approach as
create_dashboard_email_templates.py, a standalone patch since that one's
already run on this site and won't fire again to pick up a new entry.

Sent the moment someone submits the Franchise Brochure Request form -
the one email in this flow NOT handled by the Email Sequence engine,
since it's the immediate "here's what you asked for" response rather
than a scheduled follow-up step.
"""

import frappe

from dashboard.api.shared.email_templates import FRANCHISE_BROCHURE_LINK_TEMPLATE

BODY_FIELD_CANDIDATES = ["response", "response_html", "message", "content"]

SUBJECT = "Your Resilient Kid franchise brochure"
BODY = (
    "Hi {{ full_name }},\n"
    "\n"
    "Thanks for your interest in The Resilient Kid franchise! Here's your link to the brochure:\n"
    "\n"
    "{{ brochure_url }}\n"
    "\n"
    "Warm regards,\n"
    "Ashley"
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
            "Create Franchise Brochure Link Email Template - No Body Field Found",
        )
        return

    try:
        if frappe.db.exists("Email Template", FRANCHISE_BROCHURE_LINK_TEMPLATE):
            doc = frappe.get_doc("Email Template", FRANCHISE_BROCHURE_LINK_TEMPLATE)

            if not _is_blank(doc.get("subject")) or not _is_blank(doc.get(body_fieldname)):
                return

            if meta.has_field("subject"):
                doc.subject = SUBJECT

            doc.set(body_fieldname, BODY)
            doc.save(ignore_permissions=True)
        else:
            doc = frappe.new_doc("Email Template")
            doc.name = FRANCHISE_BROCHURE_LINK_TEMPLATE

            if meta.has_field("subject"):
                doc.subject = SUBJECT

            doc.set(body_fieldname, BODY)
            doc.insert(ignore_permissions=True)
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Create Franchise Brochure Link Email Template Failed: {FRANCHISE_BROCHURE_LINK_TEMPLATE}")

    frappe.db.commit()
