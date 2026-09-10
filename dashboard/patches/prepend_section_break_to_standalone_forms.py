"""
Fixes a real rendering bug on every standalone form created this batch
(School CPD Training Booking, School Training Equipment Response,
Parent Media Consent Response, School CPD Staff Feedback Response,
Staff Media Release Response, Podcast Guest Booking, Franchise
Termination Response) - each one's very first field was a plain Data
field with no Section Break before it.

Frappe's layout renderer only auto-inserts a default section for the
first field in some layouts; without an explicit Section Break leading
a Web Form's field list, the first field's container can fail to
initialise properly - its label renders, but the actual input never
appears (confirmed live: "Your Full Name" on the CPD Staff Feedback
form showed no input box at all).

The DocType + Web Form creation patches for these forms already ran on
this site (each guarded by "does this already exist"), so simply
editing them doesn't retroactively fix what's already been created -
this patch prepends the same Section Break to each existing DocType
and Web Form's field list directly. Safe and cheap: Section Break has
no backing database column, so this is a layout-only change, no data
migration involved. Skips anything that already starts with a Section
Break (a fresh site running the now-fixed creation patches for the
first time needs no correction here).
"""

import frappe

AFFECTED_DOCTYPES = [
    "School CPD Training Booking",
    "School Training Equipment Response",
    "Parent Media Consent Response",
    "School CPD Staff Feedback Response",
    "Staff Media Release Response",
    "Podcast Guest Booking",
    "Franchise Termination Response",
]


def _prepend_section_break(fields_list):
    if fields_list and fields_list[0].fieldtype == "Section Break":
        return False

    return True


def execute():
    for doctype_name in AFFECTED_DOCTYPES:
        _fix_doctype(doctype_name)
        _fix_web_form(doctype_name)

    frappe.db.commit()


def _fix_doctype(doctype_name):
    if not frappe.db.exists("DocType", doctype_name):
        return

    doc = frappe.get_doc("DocType", doctype_name)
    if not _prepend_section_break(doc.fields):
        return

    new_row = doc.append("fields", {"fieldname": "form_top_section", "fieldtype": "Section Break"})
    doc.fields.remove(new_row)
    doc.fields.insert(0, new_row)
    for idx, row in enumerate(doc.fields, start=1):
        row.idx = idx

    doc.save(ignore_permissions=True)


def _fix_web_form(doctype_name):
    web_form_name = frappe.db.get_value("Web Form", {"doc_type": doctype_name}, "name")
    if not web_form_name:
        return

    doc = frappe.get_doc("Web Form", web_form_name)
    if not _prepend_section_break(doc.web_form_fields):
        return

    new_row = doc.append("web_form_fields", {"fieldname": "form_top_section", "fieldtype": "Section Break"})
    doc.web_form_fields.remove(new_row)
    doc.web_form_fields.insert(0, new_row)
    for idx, row in enumerate(doc.web_form_fields, start=1):
        row.idx = idx

    doc.save(ignore_permissions=True)
