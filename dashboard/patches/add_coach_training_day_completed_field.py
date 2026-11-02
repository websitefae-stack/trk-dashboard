"""
Coach.training_day_completed_on - set automatically the day HQ marks a
coach's "Training Day - curriculum, Resilient Kid Values, Resilient Kid
Framework, Photoshoot" onboarding step Done (see
onboarding._stamp_training_day_completed, hooked into both
mark_step_done and mark_step_done_for_coach).

Ashley's rule: a brand new coach who hasn't been through Training Day
yet shouldn't have a legal-document compliance clock already ticking
on documents that are normally sorted out that day - so
permissions.get_expired_legal_items and legal_expiry_reminders.py both
treat a coach with no date here as fully exempt from the missing-
document grace period for all five legal document types (DBS,
Insurance, ICO Certificate, Identification, Safeguarding Certificate),
and once this date IS set, the grace period becomes 60 days (not 30)
counted from whichever is later: this date, or whenever a document was
actually first noticed missing.

A plain Date custom field (not a Table field), so this is safe
straight in patches.txt - no doctype-sync-ordering trap the way the
Identification/Safeguarding Certificate Table fields had (see
add_coach_identification_and_safeguarding_fields.py/hooks.py's
after_migrate) - this doesn't introduce any new child doctype.

Backfills every coach whose Training Day step is already Done (the
normal case - most coaches have been through Training Day long before
this field existed) using that step's own completed_on if it was ever
set, or its modified date otherwise - this app has never tracked an
exact "done" date for an HQ-marked step before now, so modified is the
closest real approximation available. A coach still mid-onboarding,
with Training Day not yet Done, is correctly left with no date here -
exactly the state that pauses their legal-document compliance clock.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import getdate

TRAINING_DAY_STEP_NAME = "Training Day - curriculum, Resilient Kid Values, Resilient Kid Framework, Photoshoot"

COACH_FIELD = {
	"fieldname": "training_day_completed_on",
	"fieldtype": "Date",
	"label": "Training Day Completed On",
	"read_only": 1,
	"insert_after": "safeguarding_certificate_missing_since",
	"module": "Dashboard",
	"description": (
		"Set automatically the day HQ marks this coach's Training Day step Done - legal-document "
		"compliance (DBS, Insurance, ICO Certificate, Identification, Safeguarding Certificate) "
		"never starts its missing-document grace period before this date."
	),
}


def execute():
	if not frappe.db.exists("DocType", "Coach"):
		return

	create_custom_fields({"Coach": [COACH_FIELD]}, ignore_validate=True)
	frappe.db.commit()

	if not frappe.db.exists("DocType", "Coach Onboarding Step"):
		return

	done_rows = frappe.get_all(
		"Coach Onboarding Step",
		filters={"step_name": TRAINING_DAY_STEP_NAME, "status": "Done"},
		fields=["coach", "completed_on", "modified"],
	)

	for row in done_rows:
		if not row.coach:
			continue

		if frappe.db.get_value("Coach", row.coach, "training_day_completed_on"):
			continue

		completed_date = getdate(row.completed_on) if row.completed_on else getdate(row.modified)
		frappe.db.set_value(
			"Coach", row.coach, "training_day_completed_on", completed_date, update_modified=False
		)

	frappe.db.commit()
