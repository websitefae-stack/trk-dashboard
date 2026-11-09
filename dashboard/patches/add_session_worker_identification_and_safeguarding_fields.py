"""
Session Worker gets the same two extra legal requirements Coach
already has (see add_coach_identification_and_safeguarding_fields.py)
- Identification (a driving licence or passport) and a Safeguarding
Certificate, both of which expire and both of which need a new one
uploaded when they do - same "legal document" treatment as the
existing DBS/Insurance requirements (see permissions.
get_expired_legal_items, legal_expiry_reminders.py, and profile.py's
LEGAL_RECORD_CONFIG/legal_parentfields, all updated alongside this
patch).

Ashley's rule for Session Worker specifically: DBS, Insurance,
Identification and Safeguarding - NOT ICO Certificate (that one's
Coach/Ashley-only, since an ICO registration is a practice-level
thing session workers don't need). See the same three files above for
where ICO Certificate was removed from Session Worker's configuration.

Table fields point at two new child doctypes this app owns (Session
Worker Identification/Session Worker Safeguarding Certificate) -
same field names as their Coach Identification/Coach Safeguarding
Certificate equivalents (id_number/identification_file,
certificate_number/safeguarding_certificate_file) since profile.py's
LEGAL_RECORD_CONFIG is shared across roles and expects those exact
names regardless of which doctype the Table field actually lives on.

Session Worker itself is a core doctype this app doesn't own the JSON
for, so new fields on it always go through create_custom_fields, same
as every other Session Worker field this app has ever added. Run from
hooks.py's after_migrate, not patches.txt, same reason and same fix
as add_coach_identification_and_safeguarding_fields.py: patches.txt
entries run before doctype sync on this site, so a Table field whose
child doctype is introduced in this same deploy would fail to create
if it ran there instead - after_migrate runs once at the very end of
`bench migrate`, after every doctype sync. Re-runs every migrate like
every other after_migrate entry; create_custom_fields is itself
idempotent (skips a field that already exists), so that's safe.

The daily 10am legal-expiry cron (legal_expiry_reminders.py) picks up
these two new fields - and starts the 30-day grace period/reminders
for every session worker currently missing both - on its own next
run, same as any other day it finds something new to check; no
separate "run it immediately" patch here, since that would depend on
this same field-creation step completing first and a patches.txt
entry can't be sequenced after after_migrate on this site.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

SESSION_WORKER_FIELDS = [
	{
		"fieldname": "identification",
		"fieldtype": "Table",
		"options": "Session Worker Identification",
		"label": "Identification",
		"insert_after": "ico_missing_since",
		"module": "Dashboard",
	},
	{
		"fieldname": "safeguarding_certificate",
		"fieldtype": "Table",
		"options": "Session Worker Safeguarding Certificate",
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
	if not frappe.db.exists("DocType", "Session Worker"):
		return

	create_custom_fields({"Session Worker": SESSION_WORKER_FIELDS}, ignore_validate=True)
	frappe.db.commit()
