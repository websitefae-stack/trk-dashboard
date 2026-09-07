"""
Replaces the never-deployed "Unlisted" idea (add_lms_course_unlisted_
field.py, removed - this supersedes it before it ever shipped) with a
single, opt-in "Show on Website" tick box per Ashley's own call: every
course always needs an account either way (signing up/logging in isn't
tied to how someone found the course), so the only real question per
course is just whether it appears in the public listing at all -
defaulting new/unmarked courses to hidden is simpler and safer than a
second "hidden but no login needed" state nobody asked for.

Backfilled to 1 for every course that's currently actually live on the
site (Published, not Restricted) so today's real catalogue doesn't
vanish the moment this deploys - only NEW courses (or ones nobody has
touched this box on) default to hidden going forward.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

LMS_COURSE_FIELDS = [
    {
        "fieldname": "custom_show_on_website",
        "fieldtype": "Check",
        "label": "Show on Website",
        "default": "0",
        "description": (
            "Tick to make this course appear in the public course listing, search and category "
            "filter. Left unticked, the course still exists and can be opened via its direct link "
            "(everyone still needs to log in or sign up to actually access it, same as any course) - "
            "it just won't be found by browsing."
        ),
        "insert_after": "custom_hq_restricted",
        "module": "Dashboard",
    },
]


def execute():
    if not frappe.db.exists("DocType", "LMS Course"):
        return

    create_custom_fields({"LMS Course": LMS_COURSE_FIELDS}, ignore_validate=True)

    frappe.db.sql(
        """
        update `tabLMS Course`
        set custom_show_on_website = 1
        where published = 1
          and ifnull(custom_hq_restricted, 0) = 0
        """
    )
    frappe.db.commit()
