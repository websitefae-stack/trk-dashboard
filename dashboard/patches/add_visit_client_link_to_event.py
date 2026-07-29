"""
Adds a proper Link field (Event.custom_visit_client -> Client) so School
Visit / Company Meeting bookings (SCHOOL_LINKED_TYPES in calendar.py) can
be tied back to the school/company they're for, without touching
Event.custom_client - that field is left deliberately blank for those two
types (see create_booking()'s comment on PACK_LINKED_SCHOOL_TYPES) so the
Package Booking Validation server script never runs its pack-balance
checks on a plain, non-billable org visit.

Without any link at all though, a School Visit/Company Meeting had no way
to resolve which client it was about after creation - the session details
sidebar showed no client, the "Email Booking Confirmation" button never
appeared, and a Google Calendar sync round-trip could incorrectly prompt
to "link a client" on an appointment that already had a school selected
when it was booked. custom_visit_client is populated at booking time for
every SCHOOL_LINKED_TYPES appointment (School Session/Company Session too,
redundantly alongside custom_client) purely so calendar.py has one
consistent field to read the "client this calendar item is about" from
for display/email/linking - never for billing.

Safe to run more than once - create_custom_fields skips any field that
already exists.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


EVENT_FIELDS = [
    {
        "fieldname": "custom_visit_client",
        "fieldtype": "Link",
        "label": "Visit Client",
        "options": "Client",
        "insert_after": "custom_client",
        "module": "Dashboard",
    },
]


def execute():
    create_custom_fields({"Event": EVENT_FIELDS}, ignore_validate=True)
    frappe.db.commit()
