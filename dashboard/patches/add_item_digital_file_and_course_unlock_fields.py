"""
Two more Item fields for the online store:

- Item.custom_digital_file (Attach) - a file Rachel attaches once on the
  product (e.g. an album download). Included as a link in the order
  confirmation email and shown in the client's portal purchase history.

- Item.custom_unlocks_lms_course (Link -> LMS Course) - buying this item
  (e.g. a "12 Session Pack") automatically enrols the buyer in the linked
  course, the same LMS Enrollment course_signup.py's own course sign-up
  flow creates, just triggered by a purchase instead of a signup form.

Safe to run more than once - create_custom_fields skips fields that
already exist.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

ITEM_FIELDS = [
    {
        "fieldname": "custom_digital_file",
        "fieldtype": "Attach",
        "label": "Digital Download File",
        "insert_after": "custom_stock_qty",
        "module": "Dashboard",
    },
    {
        "fieldname": "custom_unlocks_lms_course",
        "fieldtype": "Link",
        "label": "Unlocks Course",
        "options": "LMS Course",
        "insert_after": "custom_digital_file",
        "module": "Dashboard",
    },
]


def execute():
    if not frappe.db.exists("DocType", "LMS Course"):
        return

    create_custom_fields({"Item": ITEM_FIELDS}, ignore_validate=True)
    frappe.db.commit()
