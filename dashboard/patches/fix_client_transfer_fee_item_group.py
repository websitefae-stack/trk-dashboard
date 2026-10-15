"""
One-time correction for the "Client Transfer Fee" Item, which landed
in whatever Item Group happened to be first returned by an unfiltered
query when it was first auto-created (see client_transfers.py's
_ensure_transfer_fee_item, fixed alongside this patch to use the
Services group deliberately going forward) - on this site, that was
"Bracelet". Moves it to Services, the same group every other billable-
but-not-merch item in this app uses.
"""

import frappe


def execute():
    if not frappe.db.exists("Item", "Client Transfer Fee"):
        return

    from dashboard.api.shared.store_products import _ensure_item_group
    from dashboard.api.shared.item_access import SERVICE_ITEM_GROUP

    frappe.db.set_value(
        "Item", "Client Transfer Fee", "item_group", _ensure_item_group(SERVICE_ITEM_GROUP), update_modified=False
    )
    frappe.db.commit()
