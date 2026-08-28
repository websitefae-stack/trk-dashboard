"""
owner_type/stage/stage_sort_order/sort_order were only just added to
MASTER_STEP_LIVE_FIELDS (see onboarding.py) - before that, editing any of
them on a master step (e.g. correcting an accidentally-wrong Owner from
HQ to Coach, or repositioning a step via Sort Order Within Stage) never
reached a coach who already had that step's row, the same gap
link_url/lms_course/etc had before sync_master_step_link_fields existed.
This backfills every master step's current values onto every coach
already on that step, one time, so nothing set up before this fix is
left stuck showing the old values.
"""

import frappe

from dashboard.api.shared.onboarding import (
    ONBOARDING_STEP_DOCTYPE,
    COACH_ONBOARDING_STEP_DOCTYPE,
    MASTER_STEP_LIVE_FIELDS,
)


def execute():
    if not frappe.db.exists("DocType", ONBOARDING_STEP_DOCTYPE) or not frappe.db.exists("DocType", COACH_ONBOARDING_STEP_DOCTYPE):
        return

    try:
        _backfill()
    except Exception:
        frappe.log_error(frappe.get_traceback(), "backfill_master_step_owner_and_stage_to_coach_rows failed")


def _backfill():
    master_steps = frappe.get_all(
        ONBOARDING_STEP_DOCTYPE,
        filters={"stage": ["is", "set"]},
        fields=["name"] + MASTER_STEP_LIVE_FIELDS,
    )

    for master in master_steps:
        if not frappe.db.exists(COACH_ONBOARDING_STEP_DOCTYPE, {"onboarding_step": master.name}):
            continue

        updates = {field: master.get(field) for field in MASTER_STEP_LIVE_FIELDS}

        try:
            frappe.db.set_value(
                COACH_ONBOARDING_STEP_DOCTYPE, {"onboarding_step": master.name}, updates, update_modified=False,
            )
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Master Step Owner/Stage Backfill Failed - {master.name}")

    frappe.db.commit()
