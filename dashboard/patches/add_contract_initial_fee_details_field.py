"""
Schedule 1 of the Franchise Agreement always showed the exact same
hardcoded "£5,999 (less any deposit paid)" for every franchisee,
regardless of what they'd actually agreed - confirmed live: no way to
reflect a specific deal's real terms (e.g. Sam's £5,999 less her £1,000
deposit already paid and a £999 travel discount). The template now
renders {{ initial_fee_details }} instead (see add_franchise_agreement_
practice_document.py / update_franchise_agreement_practice_document_v7),
which needs a real field behind it on both Client Lead (the original
Franchise Agreement flow) and Recruitment Lead (its newer equivalent)
to hold that free text per lead, same read-only-set-via-the-API pattern
every other contract_* field already uses.

Safe to re-run - create_custom_fields skips a field that's already
there, standard pattern used throughout this app's own patches.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

FIELD = {
    "fieldname": "contract_initial_fee_details",
    "fieldtype": "Small Text",
    "label": "Initial Fee Details",
    "description": "Schedule 1's Initial Fee line, free text - e.g. a discount or part-paid deposit for this specific deal. Defaults to \"£5,999 (less any deposit paid)\" when blank.",
    "read_only": 1,
    "insert_after": "contract_permitted_area",
    "module": "Dashboard",
}


def execute():
    for doctype in ("Client Lead", "Recruitment Lead"):
        if not frappe.db.exists("DocType", doctype):
            continue
        if frappe.get_meta(doctype).has_field(FIELD["fieldname"]):
            continue
        create_custom_fields({doctype: [dict(FIELD)]}, ignore_validate=True)

    frappe.db.commit()
