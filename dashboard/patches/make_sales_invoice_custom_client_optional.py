"""
Sales Invoice.custom_client was somehow switched to Mandatory on this
site's live Custom Field definition - directly contradicting how every
single piece of code that touches it already treats it: webshop_
purchase.py and client_transfers.py only ever set it when there
genuinely is a Client involved, invoices.py's own save_invoice()
explicitly sets it to None when blank ("doc.custom_client = (payload.
get("custom_client") or "").strip() or None"), and a comment elsewhere
in invoices.py calls it out by name as "custom_client which can be
blank". A coach's own Coach Store order (webshop_purchase.
create_coach_store_order) has no Client at all - it's merch for the
coach personally - and was failing outright with "MandatoryError:
[Sales Invoice, ...]: custom_client" the moment that flag got set,
blocking every Coach Store order on the site.

This just restores the field to optional - it can only ever loosen
validation, never break any code path that already sets it.

Safe to run more than once.
"""

import frappe


def execute():
    if not frappe.db.exists("Custom Field", {"dt": "Sales Invoice", "fieldname": "custom_client"}):
        return

    frappe.db.set_value(
        "Custom Field",
        {"dt": "Sales Invoice", "fieldname": "custom_client"},
        "reqd",
        0,
    )
    frappe.clear_cache(doctype="Sales Invoice")
    frappe.db.commit()
