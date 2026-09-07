"""
Adds "Unlisted (Link Only)" to LMS Course - a second, deliberately
different gate from Restricted (custom_hq_restricted, added by
add_lms_course_restricted_field.py): Restricted blocks OPENING the
course to anyone who isn't enrolled/staff; Unlisted only hides it from
the public course listing/search/category filter - anyone who already
has the direct link (e.g. a QR code on physical packaging) can still
open and use it freely, no login or enrollment required. See
lms_access.py for where each is actually enforced.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

LMS_COURSE_FIELDS = [
    {
        "fieldname": "custom_unlisted",
        "fieldtype": "Check",
        "label": "Unlisted (Link Only)",
        "description": (
            "Tick to hide this course from the public course listing, search and category filter - "
            "anyone who already has the direct link can still open it freely. Unlike Restricted, this "
            "does not require enrollment or login to access."
        ),
        "insert_after": "custom_hq_restricted",
        "module": "Dashboard",
    },
]


def execute():
    if not frappe.db.exists("DocType", "LMS Course"):
        return

    create_custom_fields({"LMS Course": LMS_COURSE_FIELDS}, ignore_validate=True)
    frappe.db.commit()
