"""
Central lookup for appointment-type booking configuration, stored as
Custom Fields directly on the site's own "Appointment Template" doctype
(see patches/add_appointment_template_booking_fields.py). This means Ashley
can add a brand new appointment type, or change how an existing one
behaves (public booking on/off, slot length, whether it converts a Lead to
a Client) entirely from the Frappe desk - Appointment Template list - with
no code change required.

Coach.appointment_types.appointment_name links straight to an Appointment
Template docname, but a Lead's own appointment_type is a freeform label
picked/typed at creation time, so lookups here match by docname OR by
whichever label field the site's Appointment Template happens to use
(appointment_type / title / template_name), case-insensitive "contains" -
the same relaxed match already used across the leads/booking system.
"""

import frappe

DEFAULT_DURATION_MINUTES = 60

# Fallback only - used if this site hasn't run `bench migrate` since the
# custom fields were added yet, so public booking doesn't silently break
# in the gap between a code deploy and the next migrate.
LEGACY_EXCLUDED_LABEL_FRAGMENTS = ["supervision", "parent check"]
LEGACY_NON_CLIENT_LABEL_FRAGMENTS = ["franchisee call"]

CUSTOM_FIELDS = [
    "custom_public_booking_enabled",
    "custom_booking_duration_minutes",
    "custom_creates_client_on_conversion",
]


def _has_booking_config_fields():
    if not frappe.db.exists("DocType", "Appointment Template"):
        return False

    return frappe.get_meta("Appointment Template").has_field("custom_public_booking_enabled")


def get_matching_templates(label):
    if not label or not frappe.db.exists("DocType", "Appointment Template"):
        return []

    label_lower = label.lower()
    meta = frappe.get_meta("Appointment Template")

    candidate_fields = ["name"]
    for fieldname in ["appointment_type", "title", "template_name"]:
        if meta.has_field(fieldname):
            candidate_fields.append(fieldname)

    fetch_fields = list(candidate_fields)
    for fieldname in CUSTOM_FIELDS:
        if meta.has_field(fieldname):
            fetch_fields.append(fieldname)

    rows = frappe.get_all("Appointment Template", fields=fetch_fields, limit_page_length=1000)

    matches = []
    for row in rows:
        for fieldname in candidate_fields:
            value = row.get(fieldname) or ""
            if label_lower in value.lower():
                matches.append(row)
                break

    return matches


def is_publicly_bookable(label):
    if not label:
        return False

    label_lower = label.lower()

    # Parent Check-In and Supervision must never be publicly bookable, full
    # stop - not just as the pre-migration fallback default. Whatever
    # custom_public_booking_enabled happens to be set to on their
    # Appointment Template (e.g. left ticked from before this per-type
    # config existed, or toggled by mistake) must never be able to put a
    # staff-only appointment type on a coach's public profile page.
    if any(fragment in label_lower for fragment in LEGACY_EXCLUDED_LABEL_FRAGMENTS):
        return False

    if not _has_booking_config_fields():
        return True

    matches = get_matching_templates(label)
    return any(int(row.get("custom_public_booking_enabled") or 0) for row in matches)


def get_duration_minutes(label):
    for row in get_matching_templates(label):
        minutes = row.get("custom_booking_duration_minutes")
        if minutes:
            try:
                return int(minutes)
            except Exception:
                pass

    return DEFAULT_DURATION_MINUTES


def creates_client_on_conversion(label):
    if not label:
        return True

    if not _has_booking_config_fields():
        label_lower = label.lower()
        return not any(fragment in label_lower for fragment in LEGACY_NON_CLIENT_LABEL_FRAGMENTS)

    matches = get_matching_templates(label)
    if not matches:
        return True

    return any(int(row.get("custom_creates_client_on_conversion") if row.get("custom_creates_client_on_conversion") is not None else 1) for row in matches)
