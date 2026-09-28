"""
Adds "Give coach access to 'A Parents Course to Raising a Resilient Kid'"
to the end of Stage 3 - every new franchisee should be enrolled in this
course as part of onboarding, same as it's auto-unlocked for a client who
pays for the 12 Session Coaching Pack (see course_unlock_on_payment.py) -
but a coach doesn't buy their own pack, so nothing else in the system
ever grants them this automatically. HQ-owned, plain checkbox/status step
(no automated enrolment wired up), same as add_hq_grant_lms_access_step.py's
"Give coach access to the LMS onboarding course" for the same reason that
one is manual - not hidden from the coach here though, since this is a
benefit being given to them, not an internal plumbing prerequisite.

Placed in whatever Stage 3 is currently called (looked up from an
existing Stage 3 step at migrate time rather than hardcoded, same as
add_hq_grant_lms_access_step.py), with a Sort Order Within Stage after
both of Stage 3's existing steps (Training Day = 1, Access Your Emails =
2) but well below the dynamic Operations Manual row pinned at 1000 (see
onboarding.py's _dynamic_operations_manual_step), so it lands at the end
of Stage 3's real steps.

Idempotent, same backfill-onto-existing-coaches pattern as that patch.
"""

import frappe

from dashboard.api.shared.onboarding import _add_master_step_to_existing_coaches

ONBOARDING_STEP_DOCTYPE = "Coach Onboarding Master Step"

STEP_NAME = "Give coach access to 'A Parents Course to Raising a Resilient Kid'"
SORT_ORDER = 5
OWNER_TYPE = "HQ"
WHERE_IT_HAPPENS = "Frappe LMS"
EXPECTED_RESULT = (
    "Coach is enrolled in (or otherwise granted access to) the 'A Parents Course to Raising a "
    "Resilient Kid' LMS course, so they can access and review the material themselves."
)


def execute():
    if not frappe.db.exists("DocType", ONBOARDING_STEP_DOCTYPE):
        return

    try:
        _add_step()
    except Exception:
        frappe.log_error(frappe.get_traceback(), "add_parents_course_onboarding_step failed")


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
        frappe.log_error("No existing Stage 3 step found to match against", "add_parents_course_onboarding_step failed")
        return

    doc = frappe.get_doc({
        "doctype": ONBOARDING_STEP_DOCTYPE,
        "step_name": STEP_NAME,
        "is_active": 1,
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
