"""
Adds Event.custom_is_leadership_day - the flag create_booking() sets when
a School Session is booked with the "This is a Leadership Day (no session
pack balance required)" checkbox ticked. "Leadership Day" used to be its
own separate Calendar Item Type, selectable alongside School Session - a
franchisor had to remember which one to pick, and a real leadership day
booked that way never showed up anywhere a genuine School Session did
(reports, pack-usage views, etc) since it was a different appointment_type
entirely. This replaces that with a flag on an actual School Session
booking instead: same type everywhere it matters, just exempt from the
Package Booking Validation server script's pack-balance check (see
create_booking()'s own comment on PACK_LINKED_SCHOOL_TYPES - leaving
custom_client unset is what skips that check, same mechanism School
Visit/Company Meeting already rely on).

Safe to run more than once - create_custom_fields skips any field that
already exists.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


EVENT_FIELDS = [
    {
        "fieldname": "custom_is_leadership_day",
        "fieldtype": "Check",
        "label": "Is Leadership Day",
        "insert_after": "custom_visit_client",
        "module": "Dashboard",
    },
]


def execute():
    create_custom_fields({"Event": EVENT_FIELDS}, ignore_validate=True)
    frappe.db.commit()
