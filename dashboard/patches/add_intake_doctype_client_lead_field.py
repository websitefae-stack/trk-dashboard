"""
Adds client_lead to Intake Doctype - a Link back to the Client Lead a given
intake link was generated for. Intake Doctype is the real, live "client
intake" Web Form (built directly in Frappe Desk, not by this app) - this
field is how a submission on it gets tied back to the Lead that requested
it, via a hidden, pre-filled field on the Web Form itself (see
dashboard.api.shared.leads._intake_url / sync_intake_doctype_submission).
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

INTAKE_DOCTYPE_FIELDS = [
    {
        "fieldname": "client_lead",
        "fieldtype": "Link",
        "label": "Client Lead",
        "options": "Client Lead",
        "module": "Dashboard",
    },
]


def execute():
    if not frappe.db.exists("DocType", "Intake Doctype"):
        return

    if not frappe.db.exists("DocType", "Client Lead"):
        return

    create_custom_fields({"Intake Doctype": INTAKE_DOCTYPE_FIELDS}, ignore_validate=True)
    frappe.db.commit()
