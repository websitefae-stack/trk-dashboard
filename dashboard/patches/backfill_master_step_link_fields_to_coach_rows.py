"""
Coach Onboarding Master Step's link_url/lms_course/lms_chapter/
lms_lesson_number only ever reached a coach's already-existing Coach
Onboarding Step row via update_onboarding_step_master's own explicit
push (the franchisor Manage Step List screen) - a direct Desk edit on
the master step (e.g. wiring up LMS Course/LMS Chapter for "Access Your
Emails with Chantelle Venter") never propagated anywhere, since nothing
was listening for that save. sync_master_step_link_fields (now hooked to
Coach Onboarding Master Step.on_update) fixes this going forward; this
backfills every master step's current values onto every coach already on
that step, one time, so nothing already configured before the hook
existed is left stuck showing the old blank values.
"""

import frappe

ONBOARDING_STEP_DOCTYPE = "Coach Onboarding Master Step"
COACH_ONBOARDING_STEP_DOCTYPE = "Coach Onboarding Step"
LIVE_FIELDS = ["link_url", "lms_course", "lms_chapter", "lms_lesson_number"]


def execute():
	if not frappe.db.exists("DocType", ONBOARDING_STEP_DOCTYPE) or not frappe.db.exists("DocType", COACH_ONBOARDING_STEP_DOCTYPE):
		return

	try:
		_backfill()
	except Exception:
		frappe.log_error(frappe.get_traceback(), "backfill_master_step_link_fields_to_coach_rows failed")


def _backfill():
	master_steps = frappe.get_all(
		ONBOARDING_STEP_DOCTYPE,
		filters={"stage": ["is", "set"]},
		fields=["name"] + LIVE_FIELDS,
	)

	for master in master_steps:
		updates = {field: master.get(field) for field in LIVE_FIELDS}

		if not frappe.db.exists(COACH_ONBOARDING_STEP_DOCTYPE, {"onboarding_step": master.name}):
			continue

		try:
			frappe.db.set_value(
				COACH_ONBOARDING_STEP_DOCTYPE, {"onboarding_step": master.name}, updates, update_modified=False,
			)
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"Master Step Link Field Backfill Failed - {master.name}")

	frappe.db.commit()
