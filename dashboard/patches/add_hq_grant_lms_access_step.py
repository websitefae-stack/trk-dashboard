"""
Adds "Give coach access to the LMS onboarding course" - an HQ-owned,
hidden_from_coach step that reminds HQ to actually enrol/grant a coach
access to the (now Restricted, see add_lms_course_restricted_field.py)
LMS onboarding course before the coach reaches the "Setup Your Frappe
Profile"/"Onboarding Inside of Frappe" steps - otherwise those steps
point somewhere the coach can't open yet.

Placed in whatever Stage 3 is currently called (looked up from an
existing Stage 3 step at migrate time rather than hardcoded, since the
exact label text is Ashley's own and matching it exactly is what makes a
step actually group into the real stage - see _append_step_to_stage's
own stage-number parsing), with a deliberately negative Sort Order
Within Stage so it lands before every existing Stage 3 item without
needing to know their numbers.

Same idempotent, backfill-onto-existing-coaches pattern as
add_hq_only_clothing_sizes_step.py.
"""

import frappe

from dashboard.api.shared.onboarding import _add_master_step_to_existing_coaches

ONBOARDING_STEP_DOCTYPE = "Coach Onboarding Master Step"

STEP_NAME = "Give coach access to the LMS onboarding course"
SORT_ORDER = -10
OWNER_TYPE = "HQ"
WHERE_IT_HAPPENS = "Frappe LMS"
EXPECTED_RESULT = (
    "Coach is enrolled in (or otherwise granted access to) the Restricted LMS onboarding course, "
    "so the Setup Your Frappe Profile / Onboarding Inside of Frappe steps below actually open for them."
)


def execute():
    if not frappe.db.exists("DocType", ONBOARDING_STEP_DOCTYPE):
        return

    try:
        _add_step()
    except Exception:
        frappe.log_error(frappe.get_traceback(), "add_hq_grant_lms_access_step failed")


def _find_stage_3():
    for row in frappe.get_all(
        ONBOARDING_STEP_DOCTYPE,
        filters={"is_active": 1, "stage": ["is", "set"]},
        fields=["stage", "stage_sort_order"],
    ):
        try:
            if int((row.stage or "").split(" ")[1]) == 3:
                return row.stage, row.stage_sort_order
        except (IndexError, ValueError):
            continue
    return None, None


def _add_step():
    if frappe.db.exists(ONBOARDING_STEP_DOCTYPE, {"step_name": STEP_NAME}):
        return

    stage_label, stage_sort_order = _find_stage_3()
    if not stage_label:
        frappe.log_error("No existing Stage 3 step found to match against", "add_hq_grant_lms_access_step failed")
        return

    doc = frappe.get_doc({
        "doctype": ONBOARDING_STEP_DOCTYPE,
        "step_name": STEP_NAME,
        "is_active": 1,
        "hidden_from_coach": 1,
        "owner_type": OWNER_TYPE,
        "stage": stage_label,
        "stage_sort_order": stage_sort_order,
        "sort_order": SORT_ORDER,
        "expected_result": EXPECTED_RESULT,
        "where_it_happens": WHERE_IT_HAPPENS,
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()

    _add_master_step_to_existing_coaches(doc)
