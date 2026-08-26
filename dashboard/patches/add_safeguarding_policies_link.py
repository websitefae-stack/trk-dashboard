"""
Sets a "Go" link on the "Safeguarding + essential policies" onboarding
step, pointing straight at the coach's documents page where the actual
policies live - a concrete example of the link_url field HQ can set on
any Onboarding Step in the Desk to send a coach straight to wherever a
step needs doing (an internal Frappe page, or an external LMS/platform
URL). Also updates any Coach Onboarding Step rows already created for
this step, since those hold their own copy taken at creation time and
won't pick up a later edit to the master step automatically.
"""

import frappe

ONBOARDING_STEP_DOCTYPE = "Coach Onboarding Master Step"
COACH_ONBOARDING_STEP_DOCTYPE = "Coach Onboarding Step"

STEP_NAME = "Safeguarding + essential policies"
LINK_URL = "/coach_db/documents"


def execute():
    if not frappe.db.exists("DocType", ONBOARDING_STEP_DOCTYPE):
        return

    step_name = frappe.db.get_value(ONBOARDING_STEP_DOCTYPE, {"step_name": STEP_NAME})
    if not step_name:
        return

    frappe.db.set_value(ONBOARDING_STEP_DOCTYPE, step_name, "link_url", LINK_URL, update_modified=False)

    if frappe.db.exists("DocType", COACH_ONBOARDING_STEP_DOCTYPE):
        frappe.db.set_value(
            COACH_ONBOARDING_STEP_DOCTYPE,
            {"onboarding_step": step_name},
            "link_url",
            LINK_URL,
            update_modified=False,
        )

    frappe.db.commit()
