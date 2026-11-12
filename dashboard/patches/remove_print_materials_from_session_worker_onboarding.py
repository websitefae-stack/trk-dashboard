"""
"we need to remove the step on sw db onboarding they are not getting
print materials and business cards and stuff" - apply_coach_onboarding_
list_to_session_workers.py flipped "Create and order print materials
(flyers, business cards, roller banner)" to Applies To "Both" along
with the rest of Ashley's pasted list, but session workers don't
actually get this (coach-only branded materials). Flips it back to
Coach-only.

Goes through doc.save() (not a direct frappe.db.set_value), same
reasoning as the original flip - Coach Onboarding Master Step's own
on_update hook (onboarding.sync_master_step_active_state) only ever
ADDS a step onto existing checklists when applies_to newly includes a
role, it doesn't remove one when applies_to stops including it, so any
Session Worker Onboarding Step row already created for this step from
the earlier (incorrect) flip is deleted explicitly here too - a save
alone would leave it stranded.

Safe to re-run - no-ops once applies_to is already back to "Coach".
"""

import frappe

MASTER_STEP_DOCTYPE = "Coach Onboarding Master Step"
SESSION_WORKER_ONBOARDING_STEP_DOCTYPE = "Session Worker Onboarding Step"

STEP_NAME_FRAGMENT = "print materials"


def execute():
    if not frappe.db.exists("DocType", MASTER_STEP_DOCTYPE):
        return

    if not frappe.get_meta(MASTER_STEP_DOCTYPE).has_field("applies_to"):
        return

    names = frappe.get_all(
        MASTER_STEP_DOCTYPE,
        filters=[["step_name", "like", "%{0}%".format(STEP_NAME_FRAGMENT)]],
        pluck="name",
    )

    if not names:
        frappe.log_error(
            "No Coach Onboarding Master Step matched step_name fragment: {0!r}".format(STEP_NAME_FRAGMENT),
            "Remove Print Materials From Session Worker Onboarding - Step Not Found",
        )
        return

    for name in names:
        try:
            doc = frappe.get_doc(MASTER_STEP_DOCTYPE, name)
            if doc.applies_to != "Coach":
                doc.applies_to = "Coach"
                doc.save(ignore_permissions=True)

            if frappe.db.exists("DocType", SESSION_WORKER_ONBOARDING_STEP_DOCTYPE):
                frappe.db.delete(SESSION_WORKER_ONBOARDING_STEP_DOCTYPE, {"onboarding_step": name})
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                "Remove Print Materials From Session Worker Onboarding - Failed - {0}".format(name),
            )

    frappe.db.commit()
