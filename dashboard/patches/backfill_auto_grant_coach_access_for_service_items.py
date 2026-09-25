"""
One-off backfill for every existing service Item that should already
have been auto-granted (see item_access.py's "AUTO-GRANTING A NEW
SERVICE TO EVERY COACH" section) - this is exactly what was reported
missing: e.g. "Year 4 - Confidence Club" had Access ticked for several
coaches but Show on Site left off, because the individual per-coach
Access checkbox never set Show on Site (only the bulk "Give access to
all coaches" button did) - so it silently never showed on those
coaches' public pages. Runs the same grant every new service Item gets
automatically going forward, once, against everything that already
exists.
"""

import frappe

from dashboard.api.shared.item_access import BRAND_FIELDS, _grant_item_access_to_all_coaches_unchecked


def execute():
    if not frappe.db.exists("DocType", "Item"):
        return

    item_meta = frappe.get_meta("Item")

    if not item_meta.has_field("custom_auto_granted_coach_access"):
        return

    brand_fields = [f for f in BRAND_FIELDS if item_meta.has_field(f)]

    if not brand_fields:
        return

    or_filters = [[fieldname, "=", 1] for fieldname in brand_fields]

    items = frappe.get_all(
        "Item",
        filters={"custom_store_enabled": ["!=", 1], "custom_auto_granted_coach_access": ["!=", 1]},
        or_filters=or_filters,
        pluck="name",
    )

    for item_code in items:
        try:
            _grant_item_access_to_all_coaches_unchecked(item_code, show_on_site=True)
            frappe.db.set_value("Item", item_code, "custom_auto_granted_coach_access", 1, update_modified=False)
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Backfill Auto-Grant Coach Access Failed - {item_code}")

    frappe.db.commit()
