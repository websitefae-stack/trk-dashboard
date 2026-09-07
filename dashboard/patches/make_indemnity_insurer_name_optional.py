"""
"Indemnity" was renamed to "ICO Certificate" throughout the dashboard
(see profile.py's LEGAL_RECORD_CONFIG) since Ashley uses that field for
ICO registration, not Professional Indemnity Insurance - which is what
Coach's own "indemnity" child table was actually built for originally,
Insurer Name and all. Nothing on that side was ever changed (Coach is a
core doctype this app doesn't own the JSON for), so Insurer Name is
still a mandatory field there - a coach trying to save an ICO
Certificate (which has no insurer) hit "Value missing for: Insurer
Name" and couldn't save at all.

Looked up via frappe.get_meta() rather than hardcoding the child
doctype's name, since it isn't defined anywhere in this app's own repo.
"""

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def execute():
    if not frappe.db.exists("DocType", "Coach"):
        return

    try:
        _relax_insurer_name()
    except Exception:
        frappe.log_error(frappe.get_traceback(), "make_indemnity_insurer_name_optional failed")


def _relax_insurer_name():
    table_field = frappe.get_meta("Coach").get_field("indemnity")

    if not table_field or not table_field.options:
        return

    child_doctype = table_field.options

    if not frappe.db.exists("DocField", {"parent": child_doctype, "fieldname": "insurer_name"}):
        return

    if frappe.db.exists(
        "Property Setter", {"doc_type": child_doctype, "field_name": "insurer_name", "property": "reqd"}
    ):
        return

    make_property_setter(child_doctype, "insurer_name", "reqd", "0", "Check")
    frappe.clear_cache(doctype=child_doctype)
    frappe.db.commit()
