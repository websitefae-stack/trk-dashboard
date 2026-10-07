"""
Cleanup follow-up to add_franchise_lead_contract_fields.py - that patch
briefly included contract_trade_name/contract_trade_mark_number/
contract_initial_fee/contract_permitted_name as Ashley-supplied inputs,
before her real .docx showed Trade Name and the Trade Mark number are
fixed brand constants (not deal-specific) and Initial Fee is already a
fixed amount in the real agreement text, and Permitted Name got
simplified to just "The Resilient Kid ({{ permitted_area }})" - see the
edited add_franchise_lead_contract_fields.py and leads.get_contract_
sign_url. Removes those four now-unused fields if a `bench migrate` on
this site already created them before this correction - a no-op on a
site that only ever saw the corrected version.
"""

import frappe

STALE_FIELDNAMES = [
    "contract_trade_name",
    "contract_trade_mark_number",
    "contract_initial_fee",
    "contract_permitted_name",
]


def execute():
    if not frappe.db.exists("DocType", "Client Lead"):
        return

    for fieldname in STALE_FIELDNAMES:
        custom_field_name = frappe.db.get_value(
            "Custom Field", {"dt": "Client Lead", "fieldname": fieldname}, "name"
        )
        if custom_field_name:
            frappe.delete_doc("Custom Field", custom_field_name, ignore_permissions=True, force=True)

    frappe.clear_cache(doctype="Client Lead")
    frappe.db.commit()
