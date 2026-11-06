"""
Session Workers deliberately don't get their own individual public
profile page the way coaches do (Ashley's own call) - instead, one
shared public "Team Members" page lists every session worker who's
opted in. Adds that opt-in flag (default 0 - no existing session
worker suddenly appears publicly without Ashley choosing to show
them), reusing the same "display_on_website"-style convention Coach
Brand Access already uses for coaches' own public profile visibility.

Runs automatically on the next `bench migrate` - no manual step
needed. Safe to run more than once - create_custom_fields skips
fields that already exist.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

SESSION_WORKER_DOCTYPE = "Session Worker"

DOCTYPE_FIELDS = [
	{
		"fieldname": "show_on_team_page",
		"fieldtype": "Check",
		"label": "Show On Public Team Page",
		"default": "0",
		"module": "Dashboard",
		"description": "Lists this session worker (photo + bio) on the public Team Members page.",
	},
]


def execute():
	if not frappe.db.exists("DocType", SESSION_WORKER_DOCTYPE):
		return

	create_custom_fields({SESSION_WORKER_DOCTYPE: DOCTYPE_FIELDS}, ignore_validate=True)
	frappe.db.commit()
