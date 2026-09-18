"""
Retrofits a "Previous Stage" field onto School Sequence Enrollment (on
sites where create_school_pipeline_doctypes.py already ran) - captures
what stage the School was in immediately before this enrollment started,
so a re-engagement sequence run against an already-Customer (or
Declined/Responded/etc.) school can restore that real identity once the
sequence finishes with no response, instead of leaving/settling it at a
generic "Idle" - see school_pipeline.py's enroll_schools() and
_settle_school_stage_after_sequence().
"""

import frappe


def execute():
    if not frappe.db.exists("DocType", "School Sequence Enrollment"):
        return

    doc = frappe.get_doc("DocType", "School Sequence Enrollment")
    has_field = any(field.fieldname == "previous_stage" for field in doc.fields)

    if not has_field:
        doc.append("fields", {
            "fieldname": "previous_stage",
            "fieldtype": "Select",
            "label": "Previous Stage",
            "options": "New\nIn Sequence\nIdle\nResponded\nCall Booked\nCustomer\nDeclined",
            "read_only": 1,
            "description": "The School's stage immediately before this enrollment started - restored once the sequence finishes with no response.",
        })
        doc.save(ignore_permissions=True)

    frappe.db.commit()
