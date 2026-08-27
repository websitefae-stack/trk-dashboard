"""
Operations Manual is no longer a static "complete this in the LMS" step -
it's now pulled live from the coach's own Coach Document Requirement for
the Operations Manual Practice Document, same as Stage 5 Policies (see
_dynamic_operations_manual_step in api/shared/onboarding.py).

This retires the old static master step (deactivated, not deleted - it's
kept as a historical record, same treatment as every other step here) and
removes the stale per-coach rows it already provisioned, so an existing
coach's checklist doesn't end up showing both the old LMS-based row and
the new document-based one. Wrapped in try/except so a problem here never
blocks the rest of migrate.
"""

import frappe

ONBOARDING_STEP_DOCTYPE = "Coach Onboarding Master Step"
COACH_ONBOARDING_STEP_DOCTYPE = "Coach Onboarding Step"


def execute():
	try:
		master_names = frappe.get_all(
			ONBOARDING_STEP_DOCTYPE,
			filters={"step_name": "Operations Manual", "stage_sort_order": 3},
			pluck="name",
		)

		if not master_names:
			return

		for master_name in master_names:
			frappe.db.set_value(ONBOARDING_STEP_DOCTYPE, master_name, "is_active", 0, update_modified=False)

		stale_rows = frappe.get_all(
			COACH_ONBOARDING_STEP_DOCTYPE,
			filters={"onboarding_step": ["in", master_names]},
			pluck="name",
		)

		for row_name in stale_rows:
			try:
				frappe.delete_doc(COACH_ONBOARDING_STEP_DOCTYPE, row_name, ignore_permissions=True)
			except Exception:
				frappe.log_error(frappe.get_traceback(), f"Operations Manual Step Cleanup Failed - {row_name}")

		frappe.db.commit()
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Replace Operations Manual Step Patch Failed")
