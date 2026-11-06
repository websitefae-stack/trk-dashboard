"""
Ashley's own requirement: which coaches a session worker is allowed to
work with has to be something ONLY the franchisor sets - not derived
from whichever clients happen to already have that session worker on
them (the previous, purely computed "linked coaches"), and never
editable by a coach, since a session worker who works for one coach
only must never accidentally end up assigned to a different coach's
client.

This adds a real, persisted linked_coaches field (Table, "Session
Worker Coach" child rows) to the Session Worker doctype - the
franchisor's own roster for that session worker, set from the
Session Worker Details page. The existing computed "linked coaches"
(from Client.session_worker + Client.primary_coach/attending_coach)
is untouched and still shown separately - this field doesn't replace
it, it's the new authoritative "who are they actually approved to
work with" list that a future client-assignment picker can be
restricted to.

Runs automatically on the next `bench migrate` - no manual step
needed. Safe to run more than once - create_custom_fields skips fields
that already exist.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

SESSION_WORKER_DOCTYPE = "Session Worker"

SESSION_WORKER_FIELDS = [
	{
		"fieldname": "linked_coaches",
		"fieldtype": "Table",
		"label": "Linked Coaches",
		"module": "Dashboard",
		"options": "Session Worker Coach",
		"description": (
			"Which coach(es) this session worker is approved to work with - set by the franchisor only, "
			"from the Session Worker's own page."
		),
	},
]


def execute():
	if not frappe.db.exists("DocType", SESSION_WORKER_DOCTYPE):
		return

	create_custom_fields({SESSION_WORKER_DOCTYPE: SESSION_WORKER_FIELDS}, ignore_validate=True)
	frappe.db.commit()
