"""
Adds "Safeguarding Training with High Speed Training" as a new onboarding
step at the END of Stage 8 - Get Client Ready (after whichever steps are
currently last there - Frappe Training / Frappe Dashboard practice /
Onboarding and Offboarding Clients, see seed_onboarding_steps.py), right
before Stage 9 - Learn Your Systems begins. Ashley confirmed this exact
placement by marking it on a screenshot of a coach's own onboarding page.

Same idempotent-insert-then-backfill pattern as add_print_materials_
onboarding_step.py - seed_onboarding_steps.py's own patch only runs once
per site ever, so adding a step here needs this separate patch, both to
create the master step and to backfill a Coach Onboarding Step row onto
every coach already mid-onboarding (a coach starting fresh after this
patch runs picks it up automatically via _create_coach_onboarding_steps).

Sort order and depends_on are both worked out from whatever master step
is actually last in Stage 8 right now, rather than a hardcoded number -
robust either way, whether a given site already has all three of Stage
8's original steps active or not.
"""

import frappe

ONBOARDING_STEP_DOCTYPE = "Coach Onboarding Master Step"
COACH_ONBOARDING_STEP_DOCTYPE = "Coach Onboarding Step"

STEP_NAME = "Safeguarding Training with High Speed Training"
STAGE_LABEL = "Stage 8 - Get Client Ready"
STAGE_SORT_ORDER = 8
OWNER_TYPE = "Coach"
WHERE_IT_HAPPENS = "External (High Speed Training)"
EXPECTED_RESULT = "Safeguarding course completed on High Speed Training, certificate received."


def execute():
	if not frappe.db.exists("DocType", ONBOARDING_STEP_DOCTYPE):
		return

	try:
		_add_master_step_and_backfill()
	except Exception:
		frappe.db.rollback()
		frappe.log_error(frappe.get_traceback(), "add_safeguarding_training_onboarding_step failed")


def _last_step_in_stage_8():
	rows = frappe.get_all(
		ONBOARDING_STEP_DOCTYPE,
		filters={"stage_sort_order": STAGE_SORT_ORDER, "is_active": 1},
		fields=["name", "sort_order"],
		order_by="sort_order desc",
		limit_page_length=1,
	)
	return rows[0] if rows else None


def _add_master_step_and_backfill():
	master_name = frappe.db.get_value(ONBOARDING_STEP_DOCTYPE, {"step_name": STEP_NAME})

	if not master_name:
		last_step = _last_step_in_stage_8()
		sort_order = (last_step.sort_order + 1) if last_step else 1
		depends_on = last_step.name if last_step else None

		doc = frappe.get_doc({
			"doctype": ONBOARDING_STEP_DOCTYPE,
			"step_name": STEP_NAME,
			"is_active": 1,
			"owner_type": OWNER_TYPE,
			"stage": STAGE_LABEL,
			"stage_sort_order": STAGE_SORT_ORDER,
			"sort_order": sort_order,
			"expected_result": EXPECTED_RESULT,
			"where_it_happens": WHERE_IT_HAPPENS,
			"depends_on": depends_on,
		})
		doc.insert(ignore_permissions=True)
		master_name = doc.name
		frappe.db.commit()

	if not frappe.db.exists("DocType", COACH_ONBOARDING_STEP_DOCTYPE):
		return

	already_have_it = set(frappe.get_all(
		COACH_ONBOARDING_STEP_DOCTYPE,
		filters={"onboarding_step": master_name},
		pluck="coach",
	))

	onboarding_coaches = set(frappe.get_all(COACH_ONBOARDING_STEP_DOCTYPE, pluck="coach"))

	master = frappe.get_doc(ONBOARDING_STEP_DOCTYPE, master_name)

	for coach_name in onboarding_coaches - already_have_it:
		try:
			frappe.get_doc({
				"doctype": COACH_ONBOARDING_STEP_DOCTYPE,
				"coach": coach_name,
				"onboarding_step": master_name,
				"status": "Not Started",
				"step_name": master.step_name,
				"stage": master.stage,
				"owner_type": master.owner_type,
				"stage_sort_order": master.stage_sort_order,
				"sort_order": master.sort_order,
				"expected_result": master.expected_result,
				"where_it_happens": master.where_it_happens,
				"depends_on_step": master.depends_on,
			}).insert(ignore_permissions=True)
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"Safeguarding Training Step Backfill Failed - {coach_name}")

	frappe.db.commit()
