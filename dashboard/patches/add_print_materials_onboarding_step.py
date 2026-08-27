"""
Adds "Create and order print materials (flyers, business cards, roller
banner)" to Stage 4 - Get Business Ready, as step 5 (after the branding/
email signature steps it naturally follows). Idempotent, same pattern as
seed_onboarding_steps.py - safe to leave in place if re-run.

seed_onboarding_steps.py's own patch already ran (patches run once per
site ever), so simply adding this step to its STAGES list doesn't put it
anywhere - this inserts the master step directly, then backfills a Coach
Onboarding Step row onto every coach who's already onboarding, since a
coach who started before this patch ran would otherwise never see it (new
coaches pick it up automatically via _create_coach_onboarding_steps).
"""

import frappe

ONBOARDING_STEP_DOCTYPE = "Coach Onboarding Master Step"
COACH_ONBOARDING_STEP_DOCTYPE = "Coach Onboarding Step"

STEP_NAME = "Create and order print materials (flyers, business cards, roller banner)"
STAGE_LABEL = "Stage 4 - Get Business Ready"
STAGE_SORT_ORDER = 4
SORT_ORDER = 5
OWNER_TYPE = "HQ"
WHERE_IT_HAPPENS = "External (print supplier)"
EXPECTED_RESULT = "Materials ordered and delivered to the coach."


def execute():
	if not frappe.db.exists("DocType", ONBOARDING_STEP_DOCTYPE):
		return

	try:
		_add_master_step_and_backfill()
	except Exception:
		frappe.db.rollback()
		frappe.log_error(frappe.get_traceback(), "add_print_materials_onboarding_step failed")


def _add_master_step_and_backfill():
	master_name = frappe.db.get_value(ONBOARDING_STEP_DOCTYPE, {"step_name": STEP_NAME})

	if not master_name:
		training_day_name = frappe.db.get_value(
			ONBOARDING_STEP_DOCTYPE,
			{"step_name": "Training Day - curriculum, Resilient Kid Values, Resilient Kid Framework, Photoshoot"},
		)

		doc = frappe.get_doc({
			"doctype": ONBOARDING_STEP_DOCTYPE,
			"step_name": STEP_NAME,
			"is_active": 1,
			"owner_type": OWNER_TYPE,
			"stage": STAGE_LABEL,
			"stage_sort_order": STAGE_SORT_ORDER,
			"sort_order": SORT_ORDER,
			"expected_result": EXPECTED_RESULT,
			"where_it_happens": WHERE_IT_HAPPENS,
			"depends_on": training_day_name,
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

	for coach_name in onboarding_coaches - already_have_it:
		try:
			frappe.get_doc({
				"doctype": COACH_ONBOARDING_STEP_DOCTYPE,
				"coach": coach_name,
				"onboarding_step": master_name,
				"status": "Not Started",
				"step_name": STEP_NAME,
				"stage": STAGE_LABEL,
				"owner_type": OWNER_TYPE,
				"stage_sort_order": STAGE_SORT_ORDER,
				"sort_order": SORT_ORDER,
				"expected_result": EXPECTED_RESULT,
				"where_it_happens": WHERE_IT_HAPPENS,
				"depends_on_step": frappe.db.get_value(ONBOARDING_STEP_DOCTYPE, master_name, "depends_on"),
			}).insert(ignore_permissions=True)
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"Print Materials Step Backfill Failed - {coach_name}")

	frappe.db.commit()
