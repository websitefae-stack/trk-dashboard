"""
"those 2 can be removed from sw db onboarding" (Francesca Hammond's
drill-down, Stage 4 - Get Business Ready) - alongside "Create and
order print materials" (already undone by remove_print_materials_
from_session_worker_onboarding), "HQ processes & delivers photoshoot
images" also doesn't apply to session workers. Flips it back to
Coach-only and deletes any Session Worker Onboarding Step row already
created for it from the original (incorrect) flip.

Same reasoning/mechanism as remove_print_materials_from_session_
worker_onboarding - see that patch's own docstring for why this goes
through doc.save() and an explicit row delete rather than a plain
frappe.db.set_value.

Safe to re-run - no-ops once applies_to is already back to "Coach".
"""

import frappe

MASTER_STEP_DOCTYPE = "Coach Onboarding Master Step"
SESSION_WORKER_ONBOARDING_STEP_DOCTYPE = "Session Worker Onboarding Step"

STEP_NAME_FRAGMENT = "photoshoot images"


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
            "Remove Photoshoot Images From Session Worker Onboarding - Step Not Found",
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
                "Remove Photoshoot Images From Session Worker Onboarding - Failed - {0}".format(name),
            )

    frappe.db.commit()
