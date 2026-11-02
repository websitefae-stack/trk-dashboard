"""
Two new legal requirements for coaches (Ashley included, since she's
also a Coach record) - Identification (a driving licence or passport)
and a Safeguarding Certificate, both of which expire and both of which
need a new one uploaded when they do - same "legal document" treatment
as the existing DBS/Insurance/ICO Certificate requirements (see
permissions.get_expired_legal_items, legal_expiry_reminders.py, and
profile.py's LEGAL_RECORD_CONFIG/legal_parentfields, all updated
alongside this patch).

Coach-only (not Session Worker) - Ashley only asked for this for
coaches and herself.

Table fields point at two new child doctypes this app owns (Coach
Identification/Coach Safeguarding Certificate) - Coach itself is a
core doctype this app doesn't own the JSON for, so new fields on it
always go through create_custom_fields, same as every other Coach
field this app has ever added (see add_legal_missing_since_fields.py
for the *_missing_since pattern this one extends). Run from hooks.py's
after_migrate, not patches.txt, same reason and same fix as
add_item_gallery_field.py/add_coach_recognition_field.py: patches.txt
entries run before doctype sync on this site, so a Table field whose
child doctype is introduced in this same deploy would fail to create
if it ran there instead - after_migrate runs once at the very end of
`bench migrate`, after every doctype sync. Re-runs every migrate like
every other after_migrate entry; create_custom_fields is itself
idempotent (skips a field that already exists), so that's safe.

The daily 10am legal-expiry cron (legal_expiry_reminders.py) picks up
these two new fields - and starts the 30-day grace period/reminders
for every coach currently missing both - on its own next run, same as
any other day it finds something new to check; no separate "run it
immediately" patch here, since that would depend on this same
field-creation step completing first and a patches.txt entry can't be
sequenced after after_migrate on this site.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

COACH_FIELDS = [
	{
		"fieldname": "identification",
		"fieldtype": "Table",
		"options": "Coach Identification",
		"label": "Identification",
		"insert_after": "ico_missing_since",
		"module": "Dashboard",
	},
	{
		"fieldname": "safeguarding_certificate",
		"fieldtype": "Table",
		"options": "Coach Safeguarding Certificate",
		"label": "Safeguarding Certificate",
		"insert_after": "identification",
		"module": "Dashboard",
	},
	{
		"fieldname": "identification_missing_since",
		"fieldtype": "Date",
		"label": "Identification Missing Since",
		"read_only": 1,
		"description": (
			"Set automatically the first day no Identification record is on file - 30 days after "
			"this date, access is locked until one is uploaded."
		),
		"insert_after": "safeguarding_certificate",
		"module": "Dashboard",
	},
	{
		"fieldname": "safeguarding_certificate_missing_since",
		"fieldtype": "Date",
		"label": "Safeguarding Certificate Missing Since",
		"read_only": 1,
		"description": (
			"Set automatically the first day no Safeguarding Certificate record is on file - 30 "
			"days after this date, access is locked until one is uploaded."
		),
		"insert_after": "identification_missing_since",
		"module": "Dashboard",
	},
]


def execute():
	if not frappe.db.exists("DocType", "Coach"):
		return

	create_custom_fields({"Coach": COACH_FIELDS}, ignore_validate=True)
	frappe.db.commit()
