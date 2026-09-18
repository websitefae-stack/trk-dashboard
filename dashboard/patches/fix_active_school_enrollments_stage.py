"""
One-off data fix for schools that were already enrolled in a sequence
before enroll_schools() started always moving the school to "In Sequence"
(see add_school_sequence_enrollment_previous_stage.py) - those schools'
stage was left at whatever it was before (e.g. "Customer") instead of
"In Sequence", and their enrollment has no previous_stage recorded to
settle back to once the sequence finishes. Brings every currently-Active
enrollment in line with the new behaviour.
"""

import frappe


def execute():
    if not frappe.db.exists("DocType", "School Sequence Enrollment"):
        return

    active_enrollments = frappe.get_all(
        "School Sequence Enrollment",
        filters={"status": "Active"},
        fields=["name", "school", "previous_stage"],
    )

    for row in active_enrollments:
        if not row.school or not frappe.db.exists("School", row.school):
            continue

        current_stage = frappe.db.get_value("School", row.school, "stage")

        if current_stage == "In Sequence":
            continue

        if not row.previous_stage:
            frappe.db.set_value("School Sequence Enrollment", row.name, "previous_stage", current_stage)

        frappe.db.set_value("School", row.school, "stage", "In Sequence")

    frappe.db.commit()
