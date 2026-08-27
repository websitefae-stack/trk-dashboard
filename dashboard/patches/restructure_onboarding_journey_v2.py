"""
Reconciles the already-live Onboarding Journey to the updated structure
agreed after cross-checking the requirements workbook against the real
MemberVault module list, the journey map, and the tracking sheet:

- Trainer names appended to every LMS step, matching MemberVault exactly.
- "Social media account created" moves from Stage 2 to Stage 4, after the
  photoshoot rather than before it.
- "Safeguarding + essential policies" becomes its own stage (5), moved
  earlier so a coach reads the policies before any training starts -
  also now explicitly covers the diversity form and social media policy.
- Every stage from the old "Get Visible" onward shifts up by one to make
  room for the new Policies stage.
- "Public Speaking Training" (Catherine Sandland) added - it was on the
  journey map and confirmed as a real, current module, but was missing
  from what had been built.

Existing master records are renamed/moved in place (not deleted and
recreated) specifically so their identity is preserved - any coach
already partway through the journey keeps the same step, just relabelled,
rather than losing their status on it. Renamed/moved fields are also
pushed onto any existing Coach Onboarding Step rows already copied from
that master step, since those hold their own snapshot that a plain
master edit wouldn't otherwise reach. The one genuinely new step (Public
Speaking Training) is inserted fresh and backfilled onto every coach who
already has Stage 6 steps, so nobody already mid-journey misses it.
"""

import frappe

from dashboard.patches.seed_onboarding_steps import ONBOARDING_STEP_DOCTYPE

COACH_STEP_DOCTYPE = "Coach Onboarding Step"

# (old_step_name, new_step_name, new_stage_label, new_stage_sort_order, new_sort_order)
RENAMES = [
    ("Access Your Emails", "Access Your Emails with Chantelle Venter",
     "Stage 3 - Training Day", 3, 2),
    ("Branding Shots for Business", "Branding Shots for Business with Ali Ford",
     "Stage 3 - Training Day", 3, 3),

    ("Social media account created (setup only, not branded)", "Social media account created (setup only, not branded)",
     "Stage 4 - Get Business Ready", 4, 1),
    ("HQ processes & delivers photoshoot images", "HQ processes & delivers photoshoot images",
     "Stage 4 - Get Business Ready", 4, 2),
    ("HQ finalises social media account with branding", "HQ finalises social media account with branding",
     "Stage 4 - Get Business Ready", 4, 3),
    ("Email signature set up (with photo)", "Email signature set up (with photo)",
     "Stage 4 - Get Business Ready", 4, 4),

    ("Graphics / Canva Training", "Graphics / Canva Training with Sally Tyson",
     "Stage 6 - Get Visible", 6, 1),
    ("Social Media Training - basics", "Social Media Training - basics with Lynda Pepper",
     "Stage 6 - Get Visible", 6, 2),
    ("B-Roll Guide", "B-Roll Guide for Resilient Kid Coaches",
     "Stage 6 - Get Visible", 6, 3),
    ("LinkedIn Training", "LinkedIn Training with Helen Tudor",
     "Stage 6 - Get Visible", 6, 4),
    ("Mission-Led Content", "Mission-Led Content with Lisa Barry",
     "Stage 6 - Get Visible", 6, 5),
    ("Talking About Your Business", "Talking About Your Business with Catherine Sandland",
     "Stage 6 - Get Visible", 6, 6),
    ("The Stories We Should Be Telling", "The Stories We Should Be Telling with Catherine Sandland",
     "Stage 6 - Get Visible", 6, 7),

    ("Building a Networking Strategy", "Building a Networking Strategy with Catherine Sandland",
     "Stage 7 - Build Your Local Business", 7, 1),
    ("Networking - the C.O.N.N.E.C.T. Method", "Networking - the C.O.N.N.E.C.T. Method with Susie Sprigg",
     "Stage 7 - Build Your Local Business", 7, 2),
    ("PR Training", "PR Training with Michelle and Christian Ewan",
     "Stage 7 - Build Your Local Business", 7, 3),
    ("Confidence", "Confidence with Washington Ali",
     "Stage 7 - Build Your Local Business", 7, 4),
    ("The Marketing Momentum Circle", "The Marketing Momentum Circle with Lisa Barry",
     "Stage 7 - Build Your Local Business", 7, 5),

    ("Onboarding and Offboarding Clients", "Onboarding and Offboarding Clients",
     "Stage 8 - Get Client Ready", 8, 1),
    ("Frappe Dashboard practice (sandbox)", "Frappe Dashboard practice (sandbox)",
     "Stage 8 - Get Client Ready", 8, 2),

    ("Frappe Training", "Frappe Training with Chantelle Venter",
     "Stage 9 - Learn Your Systems", 9, 1),
    ("Live Frappe follow-up session with Chantelle", "Live Frappe follow-up session with Chantelle",
     "Stage 9 - Learn Your Systems", 9, 2),
    ("Accounting Training", "Accounting Training with Harriet Parry",
     "Stage 9 - Learn Your Systems", 9, 3),

    ("Business Coaching", "Business Coaching with Paula Cohen",
     "Stage 10 - Grow", 10, 1),
    ("Manage ADHD", "Manage ADHD with Georgia Osborne",
     "Stage 10 - Grow", 10, 2),
    ("How to WOW", "How to WOW with Nic Welsh",
     "Stage 10 - Grow", 10, 3),
    ("Fierce Principles", "Fierce Principles with Sarah Vogel",
     "Stage 10 - Grow", 10, 4),

    ("Final checks", "Final checks", "Stage 11 - Launch", 11, 1),
    ("Coaches Feedback", "Coaches Feedback", "Stage 11 - Launch", 11, 2),
    ("Certification", "Certification", "Stage 11 - Launch", 11, 3),
]

# Handled separately: moves stage, and its wording expands to cover the
# diversity form + social media policy being folded in.
SAFEGUARDING_OLD_NAME = "Safeguarding + essential policies"
SAFEGUARDING_NEW_STAGE = "Stage 5 - Policies"
SAFEGUARDING_NEW_STAGE_SORT_ORDER = 5
SAFEGUARDING_NEW_SORT_ORDER = 1
SAFEGUARDING_NEW_EXPECTED_RESULT = (
    "Mandatory policies read/acknowledged/signed as required, including the diversity information "
    "form and social media policy - done before any training starts, so the coach knows the policies "
    "up front."
)

NEW_STEP = {
    "step_name": "Public Speaking Training with Catherine Sandland",
    "owner_type": "Coach",
    "stage": "Stage 6 - Get Visible",
    "stage_sort_order": 6,
    "sort_order": 8,
    "expected_result": "Module marked complete in LMS.",
    "where_it_happens": "LMS",
}


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
        frappe.log_error(frappe.get_traceback(), "restructure_onboarding_journey_v2 failed")


def _restructure():
    for old_name, new_name, new_stage, new_stage_sort_order, new_sort_order in RENAMES:
        master_name = frappe.db.get_value(ONBOARDING_STEP_DOCTYPE, {"step_name": old_name})
        if not master_name:
            continue

        updates = {
            "step_name": new_name,
            "stage": new_stage,
            "stage_sort_order": new_stage_sort_order,
            "sort_order": new_sort_order,
        }
        frappe.db.set_value(ONBOARDING_STEP_DOCTYPE, master_name, updates, update_modified=False)
        _propagate_to_coach_rows(master_name, updates)

    safeguarding_name = frappe.db.get_value(ONBOARDING_STEP_DOCTYPE, {"step_name": SAFEGUARDING_OLD_NAME})
    if safeguarding_name:
        updates = {
            "stage": SAFEGUARDING_NEW_STAGE,
            "stage_sort_order": SAFEGUARDING_NEW_STAGE_SORT_ORDER,
            "sort_order": SAFEGUARDING_NEW_SORT_ORDER,
            "expected_result": SAFEGUARDING_NEW_EXPECTED_RESULT,
        }
        frappe.db.set_value(ONBOARDING_STEP_DOCTYPE, safeguarding_name, updates, update_modified=False)
        _propagate_to_coach_rows(safeguarding_name, updates)

    if not frappe.db.exists(ONBOARDING_STEP_DOCTYPE, {"step_name": NEW_STEP["step_name"]}):
        training_day_name = frappe.db.get_value(
            ONBOARDING_STEP_DOCTYPE,
            {"step_name": "Training Day - curriculum, Resilient Kid Values, Resilient Kid Framework, Photoshoot"},
        )

        new_master = frappe.get_doc({
            "doctype": ONBOARDING_STEP_DOCTYPE,
            "is_active": 1,
            "depends_on": training_day_name,
            **NEW_STEP,
        })
        new_master.insert(ignore_permissions=True)

        # Backfill this new step onto every coach already provisioned, so
        # someone already mid-journey doesn't just silently never see it.
        coach_names = frappe.get_all(COACH_STEP_DOCTYPE, pluck="coach", distinct=True)
        for coach_name in coach_names:
            if frappe.db.exists(COACH_STEP_DOCTYPE, {"coach": coach_name, "onboarding_step": new_master.name}):
                continue
            frappe.get_doc({
                "doctype": COACH_STEP_DOCTYPE,
                "coach": coach_name,
                "onboarding_step": new_master.name,
                "status": "Not Started",
                "step_name": new_master.step_name,
                "stage": new_master.stage,
                "owner_type": new_master.owner_type,
                "stage_sort_order": new_master.stage_sort_order,
                "sort_order": new_master.sort_order,
                "expected_result": new_master.expected_result,
                "where_it_happens": new_master.where_it_happens,
                "depends_on_step": new_master.depends_on,
            }).insert(ignore_permissions=True)

    frappe.db.commit()
