"""
Coach.recognitions (Table -> Coach Recognition) - lets a franchisor
showcase a specific coach's own achievements (e.g. being a finalist for
an award) on that coach's individual public profile page, separate from
the brand-wide Recognition page. Each row is a title + optional year/
description/badge image/link.

Registered in hooks.py's after_migrate list, not patches.txt - Coach is
a foreign doctype (defined in another app on this bench, not this one),
same ordering trap add_item_gallery_field.py's own docstring explains
for Item.custom_gallery: a Table custom field's "options" doctype
(Coach Recognition here) must already exist in the database before
create_custom_fields runs, and patches.txt entries run before this
deploy's own new doctypes are synced in, while after_migrate runs once
at the very end, after every doctype sync.

Safe to run more than once - create_custom_fields skips fields that
already exist.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

COACH_FIELDS = [
    {
        "fieldname": "recognitions",
        "fieldtype": "Table",
        "options": "Coach Recognition",
        "label": "Recognitions / Awards",
        "insert_after": "message_from_coach",
        "module": "Dashboard",
    },
]


def execute():
    if not frappe.db.exists("DocType", "Coach"):
        return

    if not frappe.db.exists("DocType", "Coach Recognition"):
        return

    try:
        create_custom_fields({"Coach": COACH_FIELDS}, ignore_validate=True)
        frappe.db.commit()
    except Exception:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "add_coach_recognition_field failed")
