"""
Course marketing pages went brand-specific for real (trh-courses plus
new trk/trt/trp/trs-courses pages in resilient_domains, each filtering
to its own brand) - this is the LMS Course equivalent of Item's own
custom_brand_hub/_kid/_teen/_people/_school (add_item_show_on_site_and_
brand_fields.py), just under the naming already used in resilient_
domains' course pages (custom_show_on_kid/_teen/_people/_school - those
three plus custom_show_on_school predate this patch, most likely added
by hand on the live site rather than tracked here, hence formalising
all five together now including the missing custom_show_on_hub).

custom_show_on_hub is backfilled to 1 for every course that's currently
actually showing on trh-courses today (Published + Show on Website) -
trh-courses is switching from "show every course, no brand filter" to
"show only Hub-tagged courses" in this same deploy, and without this
backfill every course already live on the Hub would vanish from it the
moment that filter goes live. custom_show_on_kid/_teen/_people/_school
are NOT backfilled - Ashley's already been ticking those per course by
hand, any existing values stay exactly as they are.

Safe to run more than once - create_custom_fields skips fields that
already exist.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

LMS_COURSE_FIELDS = [
    {
        "fieldname": "custom_show_on_hub",
        "fieldtype": "Check",
        "label": "Show on The Resilient Hub",
        "default": "0",
        "insert_after": "custom_show_on_website",
        "module": "Dashboard",
    },
    {
        "fieldname": "custom_show_on_kid",
        "fieldtype": "Check",
        "label": "Show on The Resilient Kid",
        "default": "0",
        "insert_after": "custom_show_on_hub",
        "module": "Dashboard",
    },
    {
        "fieldname": "custom_show_on_teen",
        "fieldtype": "Check",
        "label": "Show on The Resilient Teen",
        "default": "0",
        "insert_after": "custom_show_on_kid",
        "module": "Dashboard",
    },
    {
        "fieldname": "custom_show_on_people",
        "fieldtype": "Check",
        "label": "Show on The Resilient People",
        "default": "0",
        "insert_after": "custom_show_on_teen",
        "module": "Dashboard",
    },
    {
        "fieldname": "custom_show_on_school",
        "fieldtype": "Check",
        "label": "Show on The Resilient School",
        "default": "0",
        "insert_after": "custom_show_on_people",
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
        set custom_show_on_hub = 1
        where published = 1
          and ifnull(custom_show_on_website, 0) = 1
          and ifnull(custom_show_on_hub, 0) = 0
        """
    )
    frappe.db.commit()
