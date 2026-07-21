"""
Third wording change to the "Booking Confirmation - Resilient Kid" Email
Template (see update_booking_confirmation_template_wording.py and
remove_coach_name_from_booking_confirmation_template.py for the earlier
two) - the Meet link line now reads "Here is the Google Meet link for
easy access" instead of "you can join here", as requested. Same as those
patches, this unconditionally overwrites the template - it's a requested
wording change, not user content to preserve.

Note: this is wording only. The actual bug where a booking's Meet link
went missing from the email even when it existed was in the Python
context builder (_booking_confirmation_context() in calendar.py), not in
this template - it checked location == "online" exactly, which missed
every event booked with location "Google Meet". See
calendar.py's _is_online_location().
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
    "Here is the Google Meet link for easy access: {{ meet_link }}\n"
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
