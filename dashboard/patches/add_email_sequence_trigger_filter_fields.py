"""
Adds an optional extra qualifier to the Email Sequence engine (see
email_sequences.py / create_email_sequence_doctypes.py): trigger_
filter_field + trigger_filter_value. Until now a sequence's trigger
only matched on trigger_doctype - fine for something like "any new
Franchise Brochure Request", but not specific enough for "only
whoever bought the Primary Anxiety Toolkit", since every LMS course
purchase inserts the same "LMS Enrollment" doctype regardless of which
course it's for.

When both are set, _enrol_matching_sequences only enrols a new
document if doc.get(trigger_filter_field) == trigger_filter_value (as
a string comparison, so a Link field's docname value matches a plain
string entered in Desk) - e.g. field "course", value the Primary
Anxiety Toolkit's LMS Course docname. Left blank (the default, and
every existing sequence's current state), behaviour is unchanged -
matches on trigger_doctype alone, same as before this patch.
"""

import frappe

SEQUENCE_DOCTYPE = "Email Sequence"

NEW_FIELDS = [
    {
        "fieldname": "trigger_filter_field",
        "fieldtype": "Data",
        "label": "Only Enrol When This Fieldname... (optional)",
        "insert_after": "trigger_name_field",
        "description": (
            "Extra qualifier, e.g. \"course\" on LMS Enrollment - leave blank to "
            "enrol on every new record of the trigger doctype above, regardless "
            "of its field values."
        ),
    },
    {
        "fieldname": "trigger_filter_value",
        "fieldtype": "Data",
        "label": "...Equals This Value",
        "insert_after": "trigger_filter_field",
        "description": "e.g. the specific LMS Course's name - only used if the field above is set.",
    },
]


def execute():
    if not frappe.db.exists("DocType", SEQUENCE_DOCTYPE):
        return

    doc = frappe.get_doc("DocType", SEQUENCE_DOCTYPE)
    existing_fieldnames = {field.fieldname for field in doc.fields}

    changed = False
    for field in NEW_FIELDS:
        if field["fieldname"] not in existing_fieldnames:
            doc.append("fields", field)
            changed = True

    if changed:
        doc.save(ignore_permissions=True)
        frappe.db.commit()
