"""
Adds "Supervision" to Event.custom_session_type's fixed Select options.

_set_session_type() (calendar.py) writes this field for every appointment
type, including Supervision (see supervision_booking.py's book_supervision()
- SUPERVISION_TYPE_LABEL = "Supervision"). Without "Supervision" in the
options list, saving one throws Frappe's own field validation error
('Session Type cannot be "Supervision". It should be one of ...'), so a
Supervision self-booking could never actually be created even once a
coach/Ashley had availability configured for it.

"General" is included for the same reason - it's already offered in the
Edit Session modal (calendar_details_body.html's trkDetailEditType select)
but was missing from this list too, so saving an appointment as "General"
would hit the identical error.

Directly edits the existing Custom Field document rather than going
through create_custom_fields() - this is a change to an existing field's
options, not creating a new field, and this is unambiguous about what it
does regardless of that helper's update-existing-field behaviour.
"""

import frappe

NEW_OPTIONS = ["Supervision", "General"]


def execute():
    if not frappe.db.exists("Custom Field", {"dt": "Event", "fieldname": "custom_session_type"}):
        return

    custom_field = frappe.get_doc("Custom Field", {"dt": "Event", "fieldname": "custom_session_type"})

    if (custom_field.get("fieldtype") or "").strip() != "Select":
        return

    existing_options = [
        option.strip()
        for option in (custom_field.get("options") or "").split("\n")
        if option.strip()
    ]

    missing = [option for option in NEW_OPTIONS if option not in existing_options]

    if not missing:
        return

    custom_field.options = "\n".join(existing_options + missing)
    custom_field.save(ignore_permissions=True)
    frappe.db.commit()
