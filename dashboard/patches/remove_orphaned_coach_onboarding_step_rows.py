"""
Deleting a Coach Onboarding Master Step directly (rather than unticking
Active first) used to leave every coach's own Coach Onboarding Step row
for it stranded, pointing at a master step that no longer exists -
still counted towards total_steps in get_my_onboarding_steps, which is
why "how many steps are there" could silently drift from the real
current list after any Desk cleanup of old/duplicate master steps.
remove_coach_steps_on_master_step_delete (Coach Onboarding Master
Step.on_trash) closes this going forward; this is the one-time cleanup
for anything already orphaned before that hook existed.
"""

import frappe

ONBOARDING_STEP_DOCTYPE = "Coach Onboarding Master Step"
COACH_ONBOARDING_STEP_DOCTYPE = "Coach Onboarding Step"


def execute():
	if not frappe.db.exists("DocType", ONBOARDING_STEP_DOCTYPE) or not frappe.db.exists("DocType", COACH_ONBOARDING_STEP_DOCTYPE):
		return

	try:
		_remove_orphaned_rows()
	except Exception:
		frappe.log_error(frappe.get_traceback(), "remove_orphaned_coach_onboarding_step_rows failed")


def _remove_orphaned_rows():
	existing_master_names = set(frappe.get_all(ONBOARDING_STEP_DOCTYPE, pluck="name"))

	referenced_names = set(frappe.get_all(COACH_ONBOARDING_STEP_DOCTYPE, pluck="onboarding_step"))

	orphaned_names = [name for name in referenced_names if name and name not in existing_master_names]

	if not orphaned_names:
		return

	frappe.db.delete(COACH_ONBOARDING_STEP_DOCTYPE, {"onboarding_step": ["in", orphaned_names]})
	frappe.db.commit()
