"""
One-time cleanup: client_type is only (re)computed when a Client record is
saved through code that calls apply_age_and_client_type() - so any client
created or last edited before that logic existed can have a blank or stale
client_type even though their date_of_birth is correct. That stale value is
what lets Parent Check-In still show up as bookable for an actual Adult
client (and vice versa), since the booking modal's Adult check relies on it.

Runs automatically on the next `bench migrate` (part of a normal deploy) -
no manual step needed.
"""

import frappe

from dashboard.api.shared.client_details import (
    _AGE_DERIVED_CLIENT_TYPES,
    calculate_age_from_dob,
    get_client_type_from_age,
)


def execute():
    if not frappe.db.exists("DocType", "Client"):
        return

    meta = frappe.get_meta("Client")
    if not meta.has_field("date_of_birth") or not meta.has_field("client_type"):
        return

    rows = frappe.get_all(
        "Client",
        fields=["name", "date_of_birth", "client_type"],
        filters={"date_of_birth": ["is", "set"]},
    )

    for row in rows:
        # Franchise (and School/Company) aren't age brackets - a
        # deliberately-set administrative category must never be
        # overwritten just because a date of birth happens to be set.
        if row.client_type not in _AGE_DERIVED_CLIENT_TYPES:
            continue

        correct_type = get_client_type_from_age(calculate_age_from_dob(row.date_of_birth))
        if not correct_type or correct_type == row.client_type:
            continue

        try:
            frappe.db.set_value("Client", row.name, "client_type", correct_type, update_modified=False)
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Backfill Client Type - {row.name}")

    frappe.db.commit()
