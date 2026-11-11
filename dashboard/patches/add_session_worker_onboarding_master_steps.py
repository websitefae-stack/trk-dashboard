"""
Seeds the Session Worker side of the (now shared) Onboarding master
step list - see Coach Onboarding Master Step's new Applies To field and
onboarding.py's Session Worker provisioning.

Two things, both self-healing/idempotent:

1. Flips Training Day's existing Applies To from "Coach" to "Both" -
   Ashley's pasted list for Session Worker onboarding named this exact
   step verbatim (same text as TRAINING_DAY_STEP_NAME), confirming it's
   already the real, live step rather than something to recreate - one
   shared row now covers both roles, no duplicate.

2. Creates "Safeguarding Training with High Speed Training" as a new,
   Session Worker-only step: "Unlocks once an earlier step is done -
   this step needs to be marked as completed once the safeguarding
   certificate is uploaded to the profile. this should not be locked
   and only thing that marks it as complete is the certificate" -
   where_it_happens "Legal Record" + legal_record_fieldname
   "safeguarding_certificate" marks it Done automatically the moment a
   Session Worker Safeguarding Certificate row with its file attached
   exists (see onboarding._apply_legal_record_overrides), never by
   Mark Done, and _is_locked treats every "Legal Record" step as never
   locked regardless of Depends On - left blank here too, belt and
   braces.

Every other step Ashley listed (Email account, Your Logins hub,
Clothing sizes, the Restricted LMS onboarding course itself, Access
Your Emails/Setup Your Profile lessons, A Parent's Course access,
Operations Manual, Policies, photoshoot/signature/print materials,
Stage 8) is deliberately NOT created here - most already exist as real
Coach steps (same self-service "manage directly in Desk" design this
whole system has always had), and the right call for each (flip
Applies To to Both/Session Worker, or leave Coach-only, or add a new
Session Worker-only row with its own LMS chapter once the new 3-module
Session Worker course exists) is Ashley's own call to make from Desk -
not something to guess at from a pasted list alone.
"""

import frappe

from dashboard.api.shared.onboarding import ONBOARDING_STEP_DOCTYPE, TRAINING_DAY_STEP_NAME

SAFEGUARDING_TRAINING_STEP_NAME = "Safeguarding Training with High Speed Training"


def execute():
    if not frappe.db.exists("DocType", ONBOARDING_STEP_DOCTYPE):
        return

    if frappe.db.exists(ONBOARDING_STEP_DOCTYPE, {"step_name": TRAINING_DAY_STEP_NAME}):
        frappe.db.set_value(
            ONBOARDING_STEP_DOCTYPE, {"step_name": TRAINING_DAY_STEP_NAME}, "applies_to", "Both",
        )

    if not frappe.db.exists(ONBOARDING_STEP_DOCTYPE, {"step_name": SAFEGUARDING_TRAINING_STEP_NAME}):
        frappe.get_doc({
            "doctype": ONBOARDING_STEP_DOCTYPE,
            "step_name": SAFEGUARDING_TRAINING_STEP_NAME,
            "is_active": 1,
            "hidden_from_coach": 0,
            "owner_type": "Coach",
            "applies_to": "Session Worker",
            "stage": "Stage 9 - Safeguarding Training",
            "stage_sort_order": 9,
            "sort_order": 0,
            "expected_result": "Safeguarding course completed on High Speed Training, certificate received.",
            "where_it_happens": "Legal Record",
            "legal_record_fieldname": "safeguarding_certificate",
            "link_url": "/session_worker_db/profile",
            # Deliberately blank - see module docstring.
            "depends_on": None,
        }).insert(ignore_permissions=True)

    frappe.db.commit()
