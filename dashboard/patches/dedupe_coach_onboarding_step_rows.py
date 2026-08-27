"""
_create_coach_onboarding_steps had a real race condition: two
near-simultaneous requests for the same coach (e.g. two staff members
both opening that coach's onboarding at once) could both see "no steps
yet" and both create a full duplicate batch of 36 rows, before either
had committed. That's now fixed with a row lock (see
_create_coach_onboarding_steps), but it needs a one-time cleanup for
any duplicates it already created - this is what was actually behind
step IDs jumping around and "not found" errors on save, since a coach
could end up with several rows for the same step under different names.

For each (coach, onboarding_step) pair with more than one row: keeps
whichever row actually has progress on it (status != Not Started) if
any do, otherwise keeps the earliest-created one, and removes the
rest. Progress is never discarded by this - if more than one duplicate
somehow has progress, all but one are logged rather than silently
dropped, for a human to look at.
"""

import frappe
from collections import defaultdict

DOCTYPE = "Coach Onboarding Step"


def execute():
    if not frappe.db.exists("DocType", DOCTYPE):
        return

    try:
        _dedupe()
    except Exception:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "dedupe_coach_onboarding_step_rows failed")


def _dedupe():
    rows = frappe.get_all(
        DOCTYPE,
        fields=["name", "coach", "onboarding_step", "status", "creation"],
        order_by="creation asc",
    )

    groups = defaultdict(list)
    for row in rows:
        groups[(row.coach, row.onboarding_step)].append(row)

    for key, group_rows in groups.items():
        if len(group_rows) <= 1:
            continue

        with_progress = [row for row in group_rows if row.status != "Not Started"]

        if with_progress:
            keep = with_progress[0]
            if len(with_progress) > 1:
                frappe.log_error(
                    f"Multiple duplicate rows have progress for coach/step {key}: "
                    f"{[(row.name, row.status) for row in with_progress]} - kept {keep.name}, "
                    "review the others manually.",
                    "dedupe_coach_onboarding_step_rows",
                )
        else:
            keep = group_rows[0]

        for row in group_rows:
            if row.name == keep.name:
                continue
            try:
                frappe.delete_doc(DOCTYPE, row.name, ignore_permissions=True, force=True)
            except Exception:
                frappe.db.rollback()
                frappe.log_error(
                    frappe.get_traceback(),
                    f"dedupe_coach_onboarding_step_rows - could not delete {row.name}",
                )

    frappe.db.commit()
