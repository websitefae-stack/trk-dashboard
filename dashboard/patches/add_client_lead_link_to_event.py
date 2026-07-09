"""
Adds a proper Link field (Event.custom_client_lead -> Client Lead) so
Initial Consultation bookings made from the Leads section can be tied back
to their Client Lead directly, instead of the existing
_get_lead_for_event()-style trick of parsing "Lead: <name>" out of the
Event's own description text. Safe to run more than once - create_custom_fields
skips any field that already exists.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


EVENT_FIELDS = [
    {
        "fieldname": "custom_client_lead",
        "fieldtype": "Link",
        "label": "Client Lead",
        "options": "Client Lead",
        "insert_after": "description",
        "module": "Dashboard",
    },
]


def execute():
    create_custom_fields({"Event": EVENT_FIELDS}, ignore_validate=True)
    frappe.db.commit()
