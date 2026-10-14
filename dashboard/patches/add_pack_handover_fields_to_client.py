"""
Pack handover tracking on Client - the coach-actioned record of whether
the Kid/Teen Pack was actually handed to a new client, replacing
custom_resilient_pack_sent as the primary source of truth (see
dashboard.api.shared.coach_stock for the full feature; that field was a
plain, unused tickbox - add_client_resilient_pack_sent_field.py). It
stays put rather than being removed/replaced outright - other code/
reports may already read it - and record_pack_handover() keeps it
ticked in sync whenever a handover is recorded as "Given".

Fields inserted right after it:
- custom_pack_handover_status: Given / Could Not Give - Out of Stock /
  Not Given - Other Reason, or blank for "not yet recorded" - this blank
  state is what drives get_pending_pack_handovers()'s worklist.
- custom_pack_handover_date / _reason / _recorded_by: audit trail for
  whichever outcome was picked.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

CLIENT_FIELDS = [
    {
        "fieldname": "custom_pack_handover_status",
        "fieldtype": "Select",
        "label": "Pack Handover Status",
        "options": "\nGiven\nCould Not Give - Out of Stock\nNot Given - Other Reason",
        "insert_after": "custom_resilient_pack_sent",
        "module": "Dashboard",
    },
    {
        "fieldname": "custom_pack_handover_date",
        "fieldtype": "Date",
        "label": "Pack Handover Date",
        "insert_after": "custom_pack_handover_status",
        "module": "Dashboard",
    },
    {
        "fieldname": "custom_pack_handover_reason",
        "fieldtype": "Small Text",
        "label": "Pack Handover Reason",
        "insert_after": "custom_pack_handover_date",
        "description": "Required when status is a 'not given' reason",
        "module": "Dashboard",
    },
    {
        "fieldname": "custom_pack_handover_recorded_by",
        "fieldtype": "Link",
        "options": "User",
        "label": "Pack Handover Recorded By",
        "insert_after": "custom_pack_handover_reason",
        "read_only": 1,
        "module": "Dashboard",
    },
]


def execute():
    if not frappe.db.exists("DocType", "Client"):
        return

    create_custom_fields({"Client": CLIENT_FIELDS}, ignore_validate=True)
    frappe.db.commit()
