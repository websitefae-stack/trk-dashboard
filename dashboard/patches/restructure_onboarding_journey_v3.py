"""
Third round of adjustments to the already-live Onboarding Journey, from
Ashley's review after v2 deployed:

- Training Day's description text removed (redundant/unwanted).
- "Branding Shots for Business" and "The Marketing Momentum Circle" both
  move into Stage 6 (Get Visible), grouped with the rest of the social
  media content rather than sitting in Training Day / Build Your Local
  Business.
- "Frappe Training" (the LMS module) moves from Stage 9 into Stage 8,
  ahead of "Onboarding and Offboarding Clients" - and "Frappe Dashboard
  practice (sandbox)" moves to sit right after it, alongside the LMS
  training rather than the separate in-person follow-up session.
- "Safeguarding + essential policies" is retired as a static step -
  Stage 5 (Policies) is now built dynamically from Practice Documents at
  read time (see _dynamic_policies_stage() in api/shared/onboarding.py),
  so a coach always sees the live, current policy/procedure list rather
  than a single generic checklist line. The master step is deactivated
  rather than deleted (keeps its history), and any Coach Onboarding Step
  rows already created from it are removed - a coach's actual policy
  read/acknowledge status was always tracked on Coach Document
  Requirement anyway, so nothing is lost by removing the duplicate
  static line.
"""

import frappe

from dashboard.patches.seed_onboarding_steps import ONBOARDING_STEP_DOCTYPE

COACH_STEP_DOCTYPE = "Coach Onboarding Step"

# (step_name, new_stage_label, new_stage_sort_order, new_sort_order)
MOVES = [
    ("Branding Shots for Business with Ali Ford", "Stage 6 - Get Visible", 6, 2),
    ("Social Media Training - basics with Lynda Pepper", "Stage 6 - Get Visible", 6, 3),
    ("B-Roll Guide for Resilient Kid Coaches", "Stage 6 - Get Visible", 6, 4),
    ("LinkedIn Training with Helen Tudor", "Stage 6 - Get Visible", 6, 5),
    ("Mission-Led Content with Lisa Barry", "Stage 6 - Get Visible", 6, 6),
    ("Talking About Your Business with Catherine Sandland", "Stage 6 - Get Visible", 6, 7),
    ("The Stories We Should Be Telling with Catherine Sandland", "Stage 6 - Get Visible", 6, 8),
    ("Public Speaking Training with Catherine Sandland", "Stage 6 - Get Visible", 6, 9),
    ("The Marketing Momentum Circle with Lisa Barry", "Stage 6 - Get Visible", 6, 10),

    ("Frappe Training with Chantelle Venter", "Stage 8 - Get Client Ready", 8, 1),
    ("Frappe Dashboard practice (sandbox)", "Stage 8 - Get Client Ready", 8, 2),
    ("Onboarding and Offboarding Clients", "Stage 8 - Get Client Ready", 8, 3),

    ("Live Frappe follow-up session with Chantelle", "Stage 9 - Learn Your Systems", 9, 1),
    ("Accounting Training with Harriet Parry", "Stage 9 - Learn Your Systems", 9, 2),
]

TRAINING_DAY_NAME_MATCH = "Training Day - curriculum, Resilient Kid Values, Resilient Kid Framework, Photoshoot"

SAFEGUARDING_STEP_NAME = "Safeguarding + essential policies"


def _propagate_to_coach_rows(master_name, updates):
    if frappe.db.exists("DocType", COACH_STEP_DOCTYPE):
        frappe.db.set_value(COACH_STEP_DOCTYPE, {"onboarding_step": master_name}, updates, update_modified=False)


def execute():
    if not frappe.db.exists("DocType", ONBOARDING_STEP_DOCTYPE):
        return

    try:
        _restructure()
    except Exception:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "restructure_onboarding_journey_v3 failed")


def _restructure():
    training_day_name = frappe.db.get_value(ONBOARDING_STEP_DOCTYPE, {"step_name": TRAINING_DAY_NAME_MATCH})
    if training_day_name:
        updates = {"expected_result": ""}
        frappe.db.set_value(ONBOARDING_STEP_DOCTYPE, training_day_name, updates, update_modified=False)
        _propagate_to_coach_rows(training_day_name, updates)

    for step_name, new_stage, new_stage_sort_order, new_sort_order in MOVES:
        master_name = frappe.db.get_value(ONBOARDING_STEP_DOCTYPE, {"step_name": step_name})
        if not master_name:
            continue

        updates = {
            "stage": new_stage,
            "stage_sort_order": new_stage_sort_order,
            "sort_order": new_sort_order,
        }
        frappe.db.set_value(ONBOARDING_STEP_DOCTYPE, master_name, updates, update_modified=False)
        _propagate_to_coach_rows(master_name, updates)

    safeguarding_name = frappe.db.get_value(ONBOARDING_STEP_DOCTYPE, {"step_name": SAFEGUARDING_STEP_NAME})
    if safeguarding_name:
        frappe.db.set_value(ONBOARDING_STEP_DOCTYPE, safeguarding_name, "is_active", 0, update_modified=False)

        if frappe.db.exists("DocType", COACH_STEP_DOCTYPE):
            coach_row_names = frappe.get_all(
                COACH_STEP_DOCTYPE,
                filters={"onboarding_step": safeguarding_name},
                pluck="name",
            )
            for row_name in coach_row_names:
                try:
                    frappe.delete_doc(COACH_STEP_DOCTYPE, row_name, ignore_permissions=True, force=True)
                except Exception:
                    frappe.db.rollback()
                    frappe.log_error(
                        frappe.get_traceback(),
                        f"restructure_onboarding_journey_v3 - could not remove Safeguarding row {row_name}",
                    )

    frappe.db.commit()
