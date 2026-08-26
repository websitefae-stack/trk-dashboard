"""
Follow-up to rename_onboarding_step_doctype_away_from_core_collision:
that rename moved the WHOLE table - this app's ~36 real steps AND
whatever core-Frappe/ERPNext onboarding content was mixed into it -
under the new name "Coach Onboarding Master Step". Renaming doesn't
separate the two, so those leftover records were still there
afterwards, and still getting pulled into coach provisioning (is_active
alone never actually excluded them - see the filter fix in
_create_coach_onboarding_steps).

By this point they're safe to just remove. Once renamed away, these
rows are permanently disconnected from ERPNext's own functionality
regardless of anything done here: ERPNext's code looks for a doctype
literally called "Onboarding Step", and Frappe's own core doctype sync
will recreate a genuine, separate, empty one under that name on its own
- these leftovers were never going to reconnect to it either way.

Identified by having no `stage` - the one field only this app's real
records have ever had a value in. Same conservative approach as the
first cleanup: only removes Coach Onboarding Step rows still
"Not Started" (untouched); anything a coach has actually made progress
on is left alone and logged instead.
"""

import frappe

MASTER_DOCTYPE = "Coach Onboarding Master Step"
COACH_STEP_DOCTYPE = "Coach Onboarding Step"


def _delete_all(doctype, names):
    # Each delete is its own try/except - one record hitting an
    # unexpected constraint (e.g. some other doctype in the bench
    # linking to it) should never stop the rest of the cleanup, and
    # this whole patch has already failed a migrate and rolled back an
    # entire deploy once before over exactly this kind of thing.
    for name in names:
        try:
            frappe.delete_doc(doctype, name, ignore_permissions=True, force=True)
        except Exception:
            frappe.db.rollback()
            frappe.log_error(frappe.get_traceback(), f"purge_orphaned_master_step_leftovers - could not delete {doctype} {name}")


def _purge():
    if not frappe.db.exists("DocType", MASTER_DOCTYPE):
        return

    orphans = frappe.get_all(MASTER_DOCTYPE, filters={"stage": ["in", ["", None]]}, pluck="name")
    if not orphans:
        return

    untouched_names = orphans

    if frappe.db.exists("DocType", COACH_STEP_DOCTYPE):
        coach_rows = frappe.get_all(
            COACH_STEP_DOCTYPE,
            filters={"onboarding_step": ["in", orphans]},
            fields=["name", "status", "onboarding_step"],
        )

        touched = [row for row in coach_rows if row.status != "Not Started"]
        untouched = [row for row in coach_rows if row.status == "Not Started"]

        _delete_all(COACH_STEP_DOCTYPE, [row.name for row in untouched])

        if touched:
            frappe.log_error(
                f"Orphaned master steps left in place - coaches have progress on them: "
                f"{[(row.name, row.onboarding_step, row.status) for row in touched]}",
                "purge_orphaned_master_step_leftovers",
            )
            touched_masters = {row.onboarding_step for row in touched}
            untouched_names = [name for name in orphans if name not in touched_masters]

    _delete_all(MASTER_DOCTYPE, untouched_names)

    frappe.db.commit()


def execute():
    # This patch cleans up leftover data, not something the rest of the
    # site depends on to function - it must never be able to fail
    # migrate and roll back an entire deploy again the way an earlier
    # version of this cleanup effectively did.
    try:
        _purge()
    except Exception:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "purge_orphaned_master_step_leftovers failed")
