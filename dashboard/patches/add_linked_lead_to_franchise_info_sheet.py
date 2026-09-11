"""
Adds the "Linked Lead" field to Franchise Information Sheet Response
directly, in case create_franchise_information_sheet_form.py already
ran on this site before this field was added to it - that patch is
guarded by "does this already exist" and won't re-run to pick this up
on its own. See franchise_info_sheet.sync_franchise_info_sheet_to_lead,
which writes to this field.
"""

import frappe

DOCTYPE_NAME = "Franchise Information Sheet Response"


def execute():
    if not frappe.db.exists("DocType", DOCTYPE_NAME):
        return

    doc = frappe.get_doc("DocType", DOCTYPE_NAME)

    if any(row.fieldname == "linked_lead" for row in doc.fields):
        return

    doc.append("fields", {
        "fieldname": "linked_lead",
        "fieldtype": "Link",
        "options": "Client Lead",
        "label": "Linked Lead",
        "read_only": 1,
    })
    doc.save(ignore_permissions=True)
    frappe.db.commit()
