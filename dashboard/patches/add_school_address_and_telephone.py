"""
Retrofits "address" (Small Text) and "telephone" (Data) onto School -
create_school_pipeline_doctypes.py only creates the doctype if it
doesn't already exist, so its own updated field list doesn't apply to
sites (like production) where School was already created before this
patch existed. See add_school_area_and_deputy_head_role.py for the
same reasoning/pattern applied to "area".
"""

import frappe

NEW_FIELDS = [
    {"fieldname": "address", "fieldtype": "Small Text", "label": "Address"},
    {"fieldname": "telephone", "fieldtype": "Data", "label": "Telephone"},
]


def execute():
    if not frappe.db.exists("DocType", "School"):
        return

    doc = frappe.get_doc("DocType", "School")
    existing_fieldnames = {field.fieldname for field in doc.fields}

    changed = False
    for field in NEW_FIELDS:
        if field["fieldname"] not in existing_fieldnames:
            doc.append("fields", field)
            changed = True

    if changed:
        doc.save(ignore_permissions=True)
        frappe.db.commit()
