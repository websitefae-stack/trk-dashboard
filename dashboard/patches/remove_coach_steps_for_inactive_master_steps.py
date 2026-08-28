"""
Unticking Active on a Coach Onboarding Master Step used to only stop it
being provisioned to a coach newly starting onboarding - a coach who
already had the step kept it forever, which is why an already-unticked
step ("we no longer need this") was still showing up on a coach's
checklist. sync_master_step_active_state (Coach Onboarding Master
Step.on_update) fixes this going forward; this is the one-time cleanup
for anything already unticked before that hook existed.
"""

import frappe

ONBOARDING_STEP_DOCTYPE = "Coach Onboarding Master Step"
COACH_ONBOARDING_STEP_DOCTYPE = "Coach Onboarding Step"


def execute():
	if not frappe.db.exists("DocType", ONBOARDING_STEP_DOCTYPE) or not frappe.db.exists("DocType", COACH_ONBOARDING_STEP_DOCTYPE):
		return

	try:
		_remove_inactive_steps()
	except Exception:
		frappe.log_error(frappe.get_traceback(), "remove_coach_steps_for_inactive_master_steps failed")


def _remove_inactive_steps():
	inactive_master_names = frappe.get_all(
		ONBOARDING_STEP_DOCTYPE,
		filters={"is_active": 0, "stage": ["is", "set"]},
		pluck="name",
	)

	if not inactive_master_names:
		return

	frappe.db.delete(COACH_ONBOARDING_STEP_DOCTYPE, {"onboarding_step": ["in", inactive_master_names]})
	frappe.db.commit()
