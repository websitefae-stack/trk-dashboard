"""
Adds "School/Client Meeting" to Event.custom_session_type's fixed Select
options - same bug, same fix as add_supervision_to_session_type_options.py/
add_podcast_recording_to_session_type_options.py, which have the full
story: _set_session_type() (calendar.py) writes this field for every
appointment type. Without an appointment type's exact label in this
options list, saving its Event throws Frappe's own field validation
error ('Session Type cannot be "X". It should be one of ...').

"School/Client Meeting" is a new appointment type Ashley asked for - a
meeting with both a school/company AND a real client present, never
billed or deducted from either side's session pack (see calendar.py's
CLIENT_SESSION_TYPES/SCHOOL_LINKED_TYPES/PACK_LINKED_SCHOOL_TYPES own
comments for the full "booked as needed, not part of any pack" design).

Directly edits the existing Custom Field document rather than going
through create_custom_fields() - this is a change to an existing field's
options, not creating a new field, same reasoning as the two patches
above.
"""

import frappe

NEW_OPTIONS = ["School/Client Meeting"]


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
