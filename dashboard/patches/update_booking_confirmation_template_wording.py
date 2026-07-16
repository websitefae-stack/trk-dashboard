"""
create_dashboard_email_templates.py's seeding patch deliberately never
overwrites an Email Template that already has content, so it could never
carry this wording change to a site where the "Booking Confirmation -
Resilient Kid" template was already seeded (or hand-edited) with the old
text. This is an explicit, requested wording change to that one template
only - Intake/Invoice templates are untouched - so unlike the seeding
patch, this unconditionally overwrites it.
"""

import frappe

from dashboard.api.shared.email_templates import BOOKING_CONFIRMATION_TEMPLATE

BODY_FIELD_CANDIDATES = ["response", "response_html", "message", "content"]

SUBJECT = "Your next session with {{ coach_name }} is confirmed"
BODY = (
    "Hi {{ contact_name }},\n"
    "\n"
    "Your next session with {{ coach_name }} will take place on {{ date }} at {{ time }}"
    "{% if location_address %}, {{ location_address }}{% endif %}.\n"
    "{% if meet_link %}\n"
    "This session is online - you can join here: {{ meet_link }}\n"
    "{% endif %}\n"
    "Please let us know if you have any questions or need to make any changes.\n"
    "\n"
    "The Resilient Office"
)


def _body_fieldname(meta):
    for fieldname in BODY_FIELD_CANDIDATES:
        if meta.has_field(fieldname):
            return fieldname
    return None


def execute():
    if not frappe.db.exists("DocType", "Email Template"):
        return

    if not frappe.db.exists("Email Template", BOOKING_CONFIRMATION_TEMPLATE):
        return

    meta = frappe.get_meta("Email Template")
    body_fieldname = _body_fieldname(meta)

    if not body_fieldname:
        return

    doc = frappe.get_doc("Email Template", BOOKING_CONFIRMATION_TEMPLATE)

    if meta.has_field("subject"):
        doc.subject = SUBJECT

    doc.set(body_fieldname, BODY)
    doc.save(ignore_permissions=True)
    frappe.db.commit()
