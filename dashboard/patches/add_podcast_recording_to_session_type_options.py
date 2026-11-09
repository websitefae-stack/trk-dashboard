"""
Adds "Podcast Recording" to Event.custom_session_type's fixed Select
options - same bug, same fix as add_supervision_to_session_type_
options.py, which has the full story: _set_session_type() (calendar.py)
writes this field for every appointment type, including public coach-
profile bookings (public_booking.submit_public_booking). Without
"Podcast Recording" in the options list, saving one throws Frappe's own
field validation error ('Session Type cannot be "Podcast Recording".
It should be one of ...'), so a visitor booking a Podcast Recording
slot from a coach's public profile page got a failed booking and a
generic "Something went wrong" error (the real reason was swallowed by
a separate bug in coach-booking.js's own error handling, fixed
alongside this patch - see that file).

Directly edits the existing Custom Field document rather than going
through create_custom_fields(), same reasoning as add_supervision_to_
session_type_options.py: this is a change to an existing field's
options, not creating a new field.
"""

import frappe

NEW_OPTIONS = ["Podcast Recording"]


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
