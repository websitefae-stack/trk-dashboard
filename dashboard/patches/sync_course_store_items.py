"""
One-off backfill for _ensure_course_item (store_products.py) - creates/
syncs a backing, purchasable Item for every paid LMS Course that existed
before the LMS Course.on_update/after_insert hook did, so it can be added
to the store cart and checked out alongside physical products in one
Stripe payment. Safe to re-run: _ensure_course_item is itself idempotent.
"""

import frappe


def execute():
    if not frappe.db.exists("DocType", "LMS Course"):
        return

    from dashboard.api.shared.store_products import sync_course_store_item

    courses = frappe.get_all("LMS Course", filters={"paid_course": 1}, pluck="name")

    for course_name in courses:
        try:
            sync_course_store_item(frappe.get_doc("LMS Course", course_name))
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Course Store Item Backfill Failed - {course_name}")
