"""
Second explicit, requested wording change to the "Booking Confirmation -
Resilient Kid" Email Template (see update_booking_confirmation_template_wording.py
for the first one) - drops "with {{ coach_name }}" so the email reads "Your
next session will take place..." rather than naming a specific coach, and
only mentions the Google Meet link when the session is actually online
(is_online, set in calendar.py's _booking_confirmation_context()) instead
of whenever a meet_link happens to be present - a Home/Phone/physical
session's Event could still have a stale/irrelevant Google Meet URL on it
from before location was set, and this stops the email from ever
mentioning it. Same as that patch, this unconditionally overwrites the
template - it's a requested wording change, not user content to preserve.
"""

import frappe

from dashboard.api.shared.email_templates import BOOKING_CONFIRMATION_TEMPLATE

BODY_FIELD_CANDIDATES = ["response", "response_html", "message", "content"]

SUBJECT = "Your next session is confirmed"
BODY = (
    "Hi {{ contact_name }},\n"
    "\n"
    "Your next session will take place on {{ date }} at {{ time }}"
    "{% if location_address %}, {{ location_address }}{% endif %}.\n"
    "{% if is_online and meet_link %}\n"
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
