"""
Adds "Clothing sizes collected and ordered" to Stage 2 - Get Ready, as
step 4 (after the existing 3 items, before Stage 3 Training Day). HQ-owned
and hidden_from_coach - the coach never sees this on their own onboarding
page at all, not even as a locked/greyed-out row (see hidden_from_coach
filtering in get_my_onboarding_steps); only the franchisor drill-down
shows it, so HQ has somewhere to track getting it done.

Same idempotent pattern as add_print_materials_onboarding_step.py - safe
to leave in place if re-run, and backfills onto coaches already
onboarding via _add_master_step_to_existing_coaches (the same helper
sync_master_step_active_state uses for re-ticking Active), since a coach
who started onboarding before this patch ran would otherwise never get it.
"""

import frappe

from dashboard.api.shared.onboarding import _add_master_step_to_existing_coaches

ONBOARDING_STEP_DOCTYPE = "Coach Onboarding Master Step"

STEP_NAME = "Clothing sizes collected and ordered"
STAGE_LABEL = "Stage 2 - Get Ready"
STAGE_SORT_ORDER = 2
SORT_ORDER = 4
OWNER_TYPE = "HQ"
WHERE_IT_HAPPENS = "Manual"
EXPECTED_RESULT = "Coach's clothing sizes collected and the order placed with the supplier."


def execute():
	if not frappe.db.exists("DocType", ONBOARDING_STEP_DOCTYPE):
		return

	try:
		_add_step()
	except Exception:
		frappe.log_error(frappe.get_traceback(), "add_hq_only_clothing_sizes_step failed")


def _add_step():
	if frappe.db.exists(ONBOARDING_STEP_DOCTYPE, {"step_name": STEP_NAME}):
		return

	doc = frappe.get_doc({
		"doctype": ONBOARDING_STEP_DOCTYPE,
		"step_name": STEP_NAME,
		"is_active": 1,
		"hidden_from_coach": 1,
		"owner_type": OWNER_TYPE,
		"stage": STAGE_LABEL,
		"stage_sort_order": STAGE_SORT_ORDER,
		"sort_order": SORT_ORDER,
		"expected_result": EXPECTED_RESULT,
		"where_it_happens": WHERE_IT_HAPPENS,
	})
	doc.insert(ignore_permissions=True)
	frappe.db.commit()

	_add_master_step_to_existing_coaches(doc)
