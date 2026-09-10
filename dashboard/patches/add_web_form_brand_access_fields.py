"""
Adds the same "Brand Access" tick boxes Practice Document already has
(see practice_documents.py's PRACTICE_DOCUMENT_BRAND_FIELDS/Coach Brand
Access) onto Web Form, so a form's Links-page visibility can be scoped
to coaches with a specific brand (e.g. School/TRS) rather than only
ever "no coaches" or "every coach" - see form_reports.get_form_links.

Leaving every box unticked means no brand restriction at all (matches
Practice Document's own "no brand ticked = unrestricted" convention) -
existing forms are unaffected by this patch.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

WEB_FORM_FIELDS = [
    {
        "fieldname": "brand_access_section",
        "fieldtype": "Section Break",
        "label": "Brand Access",
        "insert_after": "custom_show_in_franchisor_reports",
        "module": "Dashboard",
        "collapsible": 1,
    },
    {
        "fieldname": "custom_brand_access_kid",
        "fieldtype": "Check",
        "label": "Kid",
        "description": (
            "Leave every Brand Access box unticked to show this form's link to every coach "
            "who already has Reports access to it (see Show In Coach Reports above). Tick one "
            "or more to restrict it further, to only coaches with that Brand Access on their "
            "own Coach record - the same brands Practice Document already uses."
        ),
        "insert_after": "brand_access_section",
        "module": "Dashboard",
    },
    {
        "fieldname": "custom_brand_access_teen",
        "fieldtype": "Check",
        "label": "Teen",
        "insert_after": "custom_brand_access_kid",
        "module": "Dashboard",
    },
    {
        "fieldname": "custom_brand_access_people",
        "fieldtype": "Check",
        "label": "People",
        "insert_after": "custom_brand_access_teen",
        "module": "Dashboard",
    },
    {
        "fieldname": "custom_brand_access_school",
        "fieldtype": "Check",
        "label": "School",
        "insert_after": "custom_brand_access_people",
        "module": "Dashboard",
    },
    {
        "fieldname": "custom_brand_access_franchise",
        "fieldtype": "Check",
        "label": "Franchise",
        "insert_after": "custom_brand_access_school",
        "module": "Dashboard",
    },
]


def execute():
    if not frappe.db.exists("DocType", "Web Form"):
        return

    create_custom_fields({"Web Form": WEB_FORM_FIELDS}, ignore_validate=True)
    frappe.db.commit()
