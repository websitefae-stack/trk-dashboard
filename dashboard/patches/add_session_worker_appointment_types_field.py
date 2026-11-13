"""
"add availability to sw db (same as coach db > profile)" - Coach's own
weekly availability (Coach.appointment_types, read by public_booking.py
and coach_availability.py) has never existed on Session Worker at all.
Session workers only ever self-book "Parent Check-In" (never Initial
Consultation/Supervision), but the mechanism is the same: a table of
weekly windows the client-portal self-booking flow reads against.

Must run after_migrate, not as a plain pre_model_sync custom-field
patch - the "Session Worker Appointment Type" child doctype (dashboard/
doctype/session_worker_appointment_type) has to already be synced to
the database before a Table field can point to it as its options.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

SESSION_WORKER_FIELDS = [
    {
        "fieldname": "appointment_types",
        "fieldtype": "Table",
        "options": "Session Worker Appointment Type",
        "label": "Availability",
        "description": "Weekly availability windows for Parent Check-In self-booking by clients via the client portal.",
        "insert_after": "linked_coaches",
        "module": "Dashboard",
    },
]


def execute():
    if not frappe.db.exists("DocType", "Session Worker"):
        return

    if not frappe.db.exists("DocType", "Session Worker Appointment Type"):
        return

    create_custom_fields({"Session Worker": SESSION_WORKER_FIELDS}, ignore_validate=True)
    frappe.db.commit()
