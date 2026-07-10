"""
Adds Custom Fields to the site's own "Appointment Template" doctype so
appointment-type booking behaviour (public booking on/off, slot length,
whether converting a Lead creates a Client) is configured from the desk
instead of hardcoded in dashboard.api.shared.appointment_types.

Backfills the known existing types to match their current hardcoded
behaviour exactly, so this never changes what's already live - it only
makes future changes/additions possible without a code deploy.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

PUBLIC_LABEL_FRAGMENTS = [
    "franchisee call",
    "initial consultation",
    "podcast recording",
    "school meeting",
]

NON_CLIENT_LABEL_FRAGMENTS = ["franchisee call"]

APPOINTMENT_TEMPLATE_FIELDS = [
    {
        "fieldname": "custom_booking_settings_section",
        "fieldtype": "Section Break",
        "label": "Dashboard Booking Settings",
        "module": "Dashboard",
    },
    {
        "fieldname": "custom_public_booking_enabled",
        "fieldtype": "Check",
        "label": "Available for Public / Self-Service Booking",
        "description": (
            "Shows this type on coach public profile pages and in a "
            "coach's own \"Add Availability\" picker. Leave unchecked for "
            "internal-only types like Supervision or Parent Check-In."
        ),
        "default": "0",
        "module": "Dashboard",
    },
    {
        "fieldname": "custom_booking_duration_minutes",
        "fieldtype": "Int",
        "label": "Booking Length (Minutes)",
        "description": "How long each booked slot is. Leave blank to use the default of 60 minutes.",
        "module": "Dashboard",
    },
    {
        "fieldname": "custom_creates_client_on_conversion",
        "fieldtype": "Check",
        "label": "Converts Lead to a Client",
        "description": (
            "Checked (default): converting a Lead of this type creates a "
            "Client + Contact as usual. Uncheck for types that lead to "
            "something else (e.g. Franchisee Call) so \"Convert to "
            "Client\" is hidden on those Leads."
        ),
        "default": "1",
        "module": "Dashboard",
    },
]


def execute():
    if not frappe.db.exists("DocType", "Appointment Template"):
        return

    create_custom_fields({"Appointment Template": APPOINTMENT_TEMPLATE_FIELDS}, ignore_validate=True)
    frappe.db.commit()

    meta = frappe.get_meta("Appointment Template")
    label_fields = [f for f in ["appointment_type", "title", "template_name"] if meta.has_field(f)]
    fields = ["name"] + label_fields

    for row in frappe.get_all("Appointment Template", fields=fields, limit_page_length=1000):
        label = ""
        for fieldname in label_fields:
            if row.get(fieldname):
                label = row.get(fieldname)
                break

        label = (label or row.get("name") or "").lower()

        if not any(fragment in label for fragment in PUBLIC_LABEL_FRAGMENTS):
            continue

        creates_client = not any(fragment in label for fragment in NON_CLIENT_LABEL_FRAGMENTS)

        try:
            frappe.db.set_value(
                "Appointment Template",
                row["name"],
                {
                    "custom_public_booking_enabled": 1,
                    "custom_booking_duration_minutes": 60,
                    "custom_creates_client_on_conversion": 1 if creates_client else 0,
                },
                update_modified=False,
            )
        except Exception:
            frappe.log_error(frappe.get_traceback(), "Backfill Appointment Template Booking Fields Failed")

    frappe.db.commit()
