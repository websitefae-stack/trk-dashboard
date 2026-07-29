"""
Lets a coach (or the franchisor, who is also backed by their own Coach
record - see profile.py's ROLE_PROFILE_CONFIG) manage their own weekly
availability windows (Coach.appointment_types), which is what the public
booking widget (public_booking.py) reads to work out bookable slots.
"""

import frappe
from frappe import _

from dashboard.api.shared.permissions import ensure_logged_in, get_current_coach_name
from dashboard.api.shared.utils import coalesce_str, coalesce_raw
from dashboard.api.shared.appointment_types import is_publicly_bookable
from dashboard.api.shared.public_booking import PORTAL_BOOKABLE_TYPES
from dashboard.api.shared.supervision_booking import SUPERVISION_TYPE_LABEL

# Parent Check-In and Supervision are deliberately excluded from
# is_publicly_bookable() - they must never appear on a coach's public
# guest-facing booking page - and neither has a real "Appointment
# Template" record (never needed one, since they're never publicly
# bookable). But a coach still has to set their own weekly availability
# for them, since that's exactly what the client-portal/staff self-booking
# slot lookups (public_booking.get_portal_slots,
# supervision_booking.get_supervision_slots) read - without an option for
# these here, a coach has no way to ever add a Coach.appointment_types row
# for them, so those bookings can never show any available times. Uses
# the exact literal labels those functions match appointment_name against
# (require_public_bookable=False's fallback), not template docnames.
STAFF_ONLY_APPOINTMENT_LABELS = sorted(set(PORTAL_BOOKABLE_TYPES) | {SUPERVISION_TYPE_LABEL})

DAY_NAMES = [
    "Monday", "Tuesday", "Wednesday", "Thursday",
    "Friday", "Saturday", "Sunday",
]


def _format_time_value(value):
    if value is None:
        return ""

    if hasattr(value, "total_seconds"):
        total_seconds = int(value.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes = remainder // 60
        return f"{hours:02d}:{minutes:02d}"

    text = str(value)
    parts = text.split(":")
    if len(parts) >= 2:
        return f"{int(parts[0]):02d}:{parts[1]}"

    return text


def _get_current_coach_doc():
    coach_name = get_current_coach_name(optional=False)
    return frappe.get_doc("Coach", coach_name)


def _get_template_label(template_name, label_cache):
    if template_name in label_cache:
        return label_cache[template_name]

    label = template_name

    if frappe.db.exists("Appointment Template", template_name):
        meta = frappe.get_meta("Appointment Template")
        for fieldname in ["appointment_type", "title", "template_name"]:
            if meta.has_field(fieldname):
                value = frappe.db.get_value("Appointment Template", template_name, fieldname)
                if value:
                    label = value
                    break

    label_cache[template_name] = label
    return label


@frappe.whitelist()
def get_appointment_template_options():
    ensure_logged_in()

    options = []
    existing_labels = set()

    if frappe.db.exists("DocType", "Appointment Template"):
        meta = frappe.get_meta("Appointment Template")
        label_field = None
        for fieldname in ["appointment_type", "title", "template_name"]:
            if meta.has_field(fieldname):
                label_field = fieldname
                break

        fields = ["name"]
        if label_field:
            fields.append(label_field)

        rows = frappe.get_all("Appointment Template", fields=fields, order_by="name asc", limit_page_length=200)

        for row in rows:
            label = (row.get(label_field) if label_field else None) or row.get("name")

            if not is_publicly_bookable(label):
                continue

            options.append({"value": row.get("name"), "label": label})
            existing_labels.add(label.lower())

    for label in STAFF_ONLY_APPOINTMENT_LABELS:
        if label.lower() in existing_labels:
            continue

        options.append({"value": label, "label": label})

    return options


@frappe.whitelist()
def get_my_availability():
    ensure_logged_in()

    coach = _get_current_coach_doc()

    if not coach.meta.has_field("appointment_types"):
        return []

    label_cache = {}
    rows = []

    for row in coach.get("appointment_types") or []:
        rows.append({
            "name": row.get("name"),
            "active": int(row.get("active") or 0),
            "appointment_name": row.get("appointment_name") or "",
            "appointment_label": _get_template_label(row.get("appointment_name"), label_cache) if row.get("appointment_name") else "",
            "day_of_the_week": row.get("day_of_the_week") or "",
            "start_time": _format_time_value(row.get("start_time")),
            "end_time": _format_time_value(row.get("end_time")),
        })

    day_order = {day: i for i, day in enumerate(DAY_NAMES)}
    rows.sort(key=lambda r: (day_order.get(r["day_of_the_week"], 99), r["start_time"]))

    return rows


def _validate_availability_input(appointment_name, day_of_the_week, start_time, end_time):
    if not appointment_name:
        frappe.throw(_("Please select an appointment type."))

    if day_of_the_week not in DAY_NAMES:
        frappe.throw(_("Please select a valid day of the week."))

    if not start_time or not end_time:
        frappe.throw(_("Please enter a start and end time."))

    if start_time >= end_time:
        frappe.throw(_("End time must be after start time."))


@frappe.whitelist()
def add_availability_row(appointment_name=None, days=None, start_time=None, end_time=None, active=1):
    """
    Accepts one or more days (e.g. Thursday and Friday, both with the same
    time window) and creates one Coach.appointment_types row per day in a
    single save, rather than making the coach repeat the whole form once
    per day.
    """
    appointment_name = coalesce_str("appointment_name", appointment_name)
    days = coalesce_raw("days", days)
    start_time = coalesce_str("start_time", start_time)
    end_time = coalesce_str("end_time", end_time)
    active = coalesce_raw("active", active)

    if isinstance(days, str):
        try:
            days = frappe.parse_json(days)
        except Exception:
            days = [d.strip() for d in days.split(",") if d.strip()]

    days = [d for d in (days or []) if d]

    if not days:
        frappe.throw(_("Please select at least one day."))

    for day in days:
        _validate_availability_input(appointment_name, day, start_time, end_time)

    coach = _get_current_coach_doc()

    if not coach.meta.has_field("appointment_types"):
        frappe.throw(_("Availability is not set up on this site yet."))

    active_value = 1 if str(active).lower() in ["1", "true", "yes", "on"] else 0

    for day in days:
        coach.append("appointment_types", {
            "active": active_value,
            "appointment_name": appointment_name,
            "day_of_the_week": day,
            "start_time": start_time,
            "end_time": end_time,
        })

    coach.save(ignore_permissions=True)
    frappe.db.commit()

    return {"ok": True, "rows": get_my_availability()}


@frappe.whitelist()
def update_availability_row(row_name=None, appointment_name=None, day_of_the_week=None, start_time=None, end_time=None, active=1):
    row_name = coalesce_str("row_name", row_name)
    appointment_name = coalesce_str("appointment_name", appointment_name)
    day_of_the_week = coalesce_str("day_of_the_week", day_of_the_week)
    start_time = coalesce_str("start_time", start_time)
    end_time = coalesce_str("end_time", end_time)
    active = coalesce_raw("active", active)

    _validate_availability_input(appointment_name, day_of_the_week, start_time, end_time)

    coach = _get_current_coach_doc()

    row = None
    for candidate in coach.get("appointment_types") or []:
        if candidate.get("name") == row_name:
            row = candidate
            break

    if not row:
        frappe.throw(_("Availability row not found."))

    row.active = 1 if str(active).lower() in ["1", "true", "yes", "on"] else 0
    row.appointment_name = appointment_name
    row.day_of_the_week = day_of_the_week
    row.start_time = start_time
    row.end_time = end_time

    coach.save(ignore_permissions=True)
    frappe.db.commit()

    return {"ok": True, "rows": get_my_availability()}


@frappe.whitelist()
def delete_availability_row(row_name=None):
    row_name = coalesce_str("row_name", row_name)

    coach = _get_current_coach_doc()

    row = None
    for candidate in coach.get("appointment_types") or []:
        if candidate.get("name") == row_name:
            row = candidate
            break

    if not row:
        frappe.throw(_("Availability row not found."))

    coach.remove(row)
    coach.save(ignore_permissions=True)
    frappe.db.commit()

    return {"ok": True, "rows": get_my_availability()}
