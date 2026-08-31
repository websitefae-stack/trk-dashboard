"""
Adds "Restricted (Enrolled/Staff Only)" directly onto Frappe LMS's own
"LMS Course" doctype - the tick box that drives lms_access.py's
permission gate. Deliberately separate from the course's own Published
checkbox: unpublishing a course blocks it for EVERYONE, including people
already enrolled in it (see lms_access.py's module docstring), which is
not what "hidden from the world, but open to whoever we've given access
to" means. A course stays Published (so LMS's own enrolled-member
handling keeps working correctly) and this field narrows who can
actually see/open it instead.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

LMS_COURSE_FIELDS = [
    {
        "fieldname": "custom_hq_restricted",
        "fieldtype": "Check",
        "label": "Restricted (Enrolled/Staff Only)",
        "description": (
            "Tick to hide this course from the public course catalogue and block anyone from "
            "opening it unless they're already enrolled, an instructor on it, or a Moderator - "
            "keep Published ticked too, this works alongside it rather than replacing it."
        ),
        "insert_after": "published",
        "module": "Dashboard",
    },
]


def execute():
    if not frappe.db.exists("DocType", "LMS Course"):
        return

    create_custom_fields({"LMS Course": LMS_COURSE_FIELDS}, ignore_validate=True)
    frappe.db.commit()
