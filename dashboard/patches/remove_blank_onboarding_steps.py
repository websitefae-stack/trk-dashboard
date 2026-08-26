"""
The live site had 48 Onboarding Step records where only 36 were ever
seeded by seed_onboarding_steps.py - the other 12 are almost certainly
stray/test records created directly in the Desk (e.g. clicking "New"
and not filling it in, or a duplicate that didn't get finished). A
record with no step_name is useless by definition - it can never
display or mean anything to a coach - and any Coach Onboarding Step
created from one is why some coaches were seeing entirely blank rows
that the self-heal in get_my_onboarding_steps couldn't fix (there's
nothing valid to copy from a master that's blank itself).

This removes any Onboarding Step with a blank step_name, along with
any Coach Onboarding Step rows pointing at it - but only those still
"Not Started" (untouched, safe to discard). A row a coach has actually
made progress on is left alone (and the blank master it points to is
left in place too, so the link doesn't break) and logged instead, so
nothing a coach has done gets silently lost.
"""

import frappe

ONBOARDING_STEP_DOCTYPE = "Coach Onboarding Master Step"
COACH_ONBOARDING_STEP_DOCTYPE = "Coach Onboarding Step"


def execute():
    if not frappe.db.exists("DocType", ONBOARDING_STEP_DOCTYPE):
        return

    blank_steps = frappe.get_all(ONBOARDING_STEP_DOCTYPE, filters={"step_name": ["in", ["", None]]}, pluck="name")
    if not blank_steps:
        return

    untouched_names = []

    if frappe.db.exists("DocType", COACH_ONBOARDING_STEP_DOCTYPE):
        coach_rows = frappe.get_all(
            COACH_ONBOARDING_STEP_DOCTYPE,
            filters={"onboarding_step": ["in", blank_steps]},
            fields=["name", "status", "onboarding_step"],
        )

        touched = [row for row in coach_rows if row.status != "Not Started"]
        untouched = [row for row in coach_rows if row.status == "Not Started"]

        for row in untouched:
            frappe.delete_doc(COACH_ONBOARDING_STEP_DOCTYPE, row.name, ignore_permissions=True, force=True)

        if touched:
            frappe.log_error(
                f"Blank Onboarding Step masters left in place - coaches have progress on them: "
                f"{[(row.name, row.onboarding_step, row.status) for row in touched]}",
                "remove_blank_onboarding_steps",
            )
            touched_masters = {row.onboarding_step for row in touched}
            untouched_names = [name for name in blank_steps if name not in touched_masters]
        else:
            untouched_names = blank_steps
    else:
        untouched_names = blank_steps

    for name in untouched_names:
        frappe.delete_doc(ONBOARDING_STEP_DOCTYPE, name, ignore_permissions=True, force=True)

    frappe.db.commit()
