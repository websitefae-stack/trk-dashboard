"""
Adds "Podcast Recording" and "Franchisee Call" to Event.custom_
session_type's fixed Select options - same bug, same fix as add_
supervision_to_session_type_options.py, which has the full story:
_set_session_type() (calendar.py) writes this field for every
appointment type, including public coach-profile bookings
(public_booking.submit_public_booking). Without an appointment type's
exact label in this options list, saving its Event throws Frappe's own
field validation error ('Session Type cannot be "X". It should be one
of ...'), so a visitor booking it from a coach's public profile page
gets a failed booking and (before a separate fix to coach-booking.js's
own error handling) just a generic "Something went wrong" error
instead of anything pointing at the real cause.

"Podcast Recording" was caught from a guest's actual failed booking.
"Franchisee Call" was caught the same way immediately after - Ashley's
own live test before deploying, same symptom, confirmed from the raw
network response. Both are long-established, heavily used appointment
types (Franchisee Call drives this app's entire franchise recruitment
pipeline - see leads.py) that had simply never been added here.

This options list has no mechanism that keeps it in sync with
Coach.appointment_types/Appointment Template - every *new* appointment
type Ashley sets up from Desk risks hitting this exact same wall again
until it's separately added here. Flagged to her as a known structural
gap, not something this patch itself can close for good.

Directly edits the existing Custom Field document rather than going
through create_custom_fields(), same reasoning as add_supervision_to_
session_type_options.py: this is a change to an existing field's
options, not creating a new field.
"""

import frappe

NEW_OPTIONS = ["Podcast Recording", "Franchisee Call"]


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
