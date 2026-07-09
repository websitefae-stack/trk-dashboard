"""
Guest-facing (no login) booking for a public "Initial Consultation" slot
picker on a coach's public profile page (resilient_domains). Deliberately
self-contained rather than reusing calendar.create_booking() - that
function assumes a logged-in coach/session-worker session
(_require_logged_in_user()) and carries a lot of internal-dashboard-only
complexity (recurring bookings, additional workers, school/company
billing, travel charges) that doesn't apply here. This only ever creates
a single, non-recurring Initial Consultation Event plus its Client Lead,
mirroring the shape calendar.py itself builds for that appointment type.
"""

import calendar as _calendar_module

import frappe
from frappe import _
from frappe.utils import get_datetime, add_to_date, getdate, now_datetime

from dashboard.api.shared.utils import coalesce_str
from dashboard.api.shared.notifications import create_trk_notification

INITIAL_CONSULTATION_LABEL = "Initial Consultation"
INITIAL_CONSULTATION_DURATION_MINUTES = 60
SLOT_GRID_MINUTES = 30
MAX_DAYS_AHEAD = 60

DAY_NAMES = [
    "Monday", "Tuesday", "Wednesday", "Thursday",
    "Friday", "Saturday", "Sunday",
]


def _format_time_value(value):
    """Coach.appointment_types.start_time/end_time are Time fields, which
    Frappe loads as datetime.timedelta - normalise to 'HH:MM:SS' either way."""
    if value is None:
        return None

    if hasattr(value, "total_seconds"):
        total_seconds = int(value.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    return str(value)


def _get_initial_consultation_template_names():
    """
    Case-insensitive "contains" match rather than an exact-name match -
    matches the same relaxed check used on the coach profile page
    template, so a template named e.g. "Initial Consultation (Online)" or
    lowercase "initial consultation" still gets picked up on both sides
    instead of the button silently doing nothing.
    """
    if not frappe.db.exists("DocType", "Appointment Template"):
        return set()

    label = INITIAL_CONSULTATION_LABEL.lower()
    meta = frappe.get_meta("Appointment Template")

    candidate_fields = ["name"]
    for fieldname in ["appointment_type", "title", "template_name"]:
        if meta.has_field(fieldname):
            candidate_fields.append(fieldname)

    rows = frappe.get_all("Appointment Template", fields=candidate_fields, limit_page_length=1000)

    names = set()
    for row in rows:
        for fieldname in candidate_fields:
            value = (row.get(fieldname) or "")
            if label in value.lower():
                names.add(row.get("name"))
                break

    return names


def _get_coach_windows_for_date(coach, date_str):
    if not frappe.db.exists("Coach", coach):
        return []

    coach_meta = frappe.get_meta("Coach")
    if not coach_meta.has_field("appointment_types"):
        return []

    template_names = _get_initial_consultation_template_names()
    if not template_names:
        return []

    day_name = DAY_NAMES[getdate(date_str).weekday()]

    coach_doc = frappe.get_doc("Coach", coach)
    windows = []

    for row in coach_doc.get("appointment_types") or []:
        if not row.get("active"):
            continue

        if (row.get("day_of_the_week") or "").strip() != day_name:
            continue

        if row.get("appointment_name") not in template_names:
            continue

        start_time = _format_time_value(row.get("start_time"))
        end_time = _format_time_value(row.get("end_time"))

        if not start_time or not end_time:
            continue

        windows.append((start_time, end_time))

    return windows


def _get_coach_booked_windows(coach_user, date_str):
    if not coach_user:
        return []

    day_start = get_datetime(f"{date_str} 00:00:00")
    day_end = get_datetime(f"{date_str} 23:59:59")

    events = frappe.get_all(
        "Event",
        filters=[
            ["owner", "=", coach_user],
            ["starts_on", "<", day_end],
            ["ends_on", ">", day_start],
        ],
        fields=["starts_on", "ends_on"],
        ignore_permissions=True,
    )

    return [(event.starts_on, event.ends_on) for event in events]


def _get_coach_user(coach):
    return frappe.db.get_value("Coach", coach, "user") or frappe.db.get_value("Coach", coach, "coach_email")


def _compute_available_slots(coach, date_str):
    windows = _get_coach_windows_for_date(coach, date_str)
    if not windows:
        return []

    coach_user = _get_coach_user(coach)
    booked = _get_coach_booked_windows(coach_user, date_str)
    now = now_datetime()

    slots = []

    for start_time, end_time in windows:
        window_start = get_datetime(f"{date_str} {start_time}")
        window_end = get_datetime(f"{date_str} {end_time}")
        cursor = window_start

        while True:
            slot_end = add_to_date(cursor, minutes=INITIAL_CONSULTATION_DURATION_MINUTES)
            if slot_end > window_end:
                break

            if cursor > now:
                conflict = any(
                    cursor < booked_end and slot_end > booked_start
                    for booked_start, booked_end in booked
                )
                if not conflict and cursor.strftime("%H:%M") not in slots:
                    slots.append(cursor.strftime("%H:%M"))

            cursor = add_to_date(cursor, minutes=SLOT_GRID_MINUTES)

    slots.sort()
    return slots


@frappe.whitelist(allow_guest=True)
def get_available_slots(coach=None, date=None):
    coach = coalesce_str("coach", coach)
    date = coalesce_str("date", date)

    if not coach or not date:
        return []

    try:
        requested = getdate(date)
    except Exception:
        return []

    if requested < getdate(now_datetime()) or (requested - getdate(now_datetime())).days > MAX_DAYS_AHEAD:
        return []

    return _compute_available_slots(coach, date)


def _get_windows_by_weekday(coach):
    """Same as _get_coach_windows_for_date, but grouped by weekday and
    computed once - used by the month view so it doesn't reload the Coach
    doc once per day of the month."""
    if not frappe.db.exists("Coach", coach):
        return {}

    coach_meta = frappe.get_meta("Coach")
    if not coach_meta.has_field("appointment_types"):
        return {}

    template_names = _get_initial_consultation_template_names()
    if not template_names:
        return {}

    coach_doc = frappe.get_doc("Coach", coach)
    by_weekday = {day: [] for day in DAY_NAMES}

    for row in coach_doc.get("appointment_types") or []:
        if not row.get("active"):
            continue

        day_name = (row.get("day_of_the_week") or "").strip()
        if day_name not in by_weekday:
            continue

        if row.get("appointment_name") not in template_names:
            continue

        start_time = _format_time_value(row.get("start_time"))
        end_time = _format_time_value(row.get("end_time"))

        if not start_time or not end_time:
            continue

        by_weekday[day_name].append((start_time, end_time))

    return by_weekday


@frappe.whitelist(allow_guest=True)
def get_available_dates(coach=None, year=None, month=None):
    """Which dates in the given month have at least one open Initial
    Consultation slot, for greying out empty days in the calendar picker."""
    coach = coalesce_str("coach", coach)
    year = coalesce_str("year", year)
    month = coalesce_str("month", month)

    if not coach or not year or not month:
        return []

    try:
        year = int(year)
        month = int(month)
    except Exception:
        return []

    windows_by_weekday = _get_windows_by_weekday(coach)
    if not any(windows_by_weekday.values()):
        return []

    coach_user = _get_coach_user(coach)
    if not coach_user:
        return []

    days_in_month = _calendar_module.monthrange(year, month)[1]
    month_start = get_datetime(f"{year:04d}-{month:02d}-01 00:00:00")
    month_end = add_to_date(month_start, days=days_in_month)

    events = frappe.get_all(
        "Event",
        filters=[
            ["owner", "=", coach_user],
            ["starts_on", "<", month_end],
            ["ends_on", ">", month_start],
        ],
        fields=["starts_on", "ends_on"],
        ignore_permissions=True,
    )

    booked_by_date = {}
    for event in events:
        date_key = event.starts_on.strftime("%Y-%m-%d")
        booked_by_date.setdefault(date_key, []).append((event.starts_on, event.ends_on))

    now = now_datetime()
    today = getdate(now)
    available_dates = []

    for day in range(1, days_in_month + 1):
        date_obj = getdate(f"{year:04d}-{month:02d}-{day:02d}")

        if date_obj < today or (date_obj - today).days > MAX_DAYS_AHEAD:
            continue

        day_name = DAY_NAMES[date_obj.weekday()]
        windows = windows_by_weekday.get(day_name) or []
        if not windows:
            continue

        date_str = date_obj.strftime("%Y-%m-%d")
        booked = booked_by_date.get(date_str, [])

        for start_time, end_time in windows:
            window_start = get_datetime(f"{date_str} {start_time}")
            window_end = get_datetime(f"{date_str} {end_time}")
            cursor = window_start
            found = False

            while True:
                slot_end = add_to_date(cursor, minutes=INITIAL_CONSULTATION_DURATION_MINUTES)
                if slot_end > window_end:
                    break

                if cursor > now:
                    conflict = any(
                        cursor < booked_end and slot_end > booked_start
                        for booked_start, booked_end in booked
                    )
                    if not conflict:
                        found = True
                        break

                cursor = add_to_date(cursor, minutes=SLOT_GRID_MINUTES)

            if found:
                available_dates.append(date_str)
                break

    return available_dates


@frappe.whitelist(allow_guest=True)
def submit_public_booking(
    coach=None,
    date=None,
    time=None,
    contact_name=None,
    client_name=None,
    contact_mobile=None,
    contact_email=None,
    enquiry_reason=None,
):
    coach = coalesce_str("coach", coach)
    date = coalesce_str("date", date)
    time = coalesce_str("time", time)
    contact_name = coalesce_str("contact_name", contact_name)
    client_name = coalesce_str("client_name", client_name)
    contact_mobile = coalesce_str("contact_mobile", contact_mobile)
    contact_email = coalesce_str("contact_email", contact_email)
    enquiry_reason = coalesce_str("enquiry_reason", enquiry_reason)

    if not coach or not frappe.db.exists("Coach", coach):
        frappe.throw(_("This coach was not found."))

    if not date or not time:
        frappe.throw(_("Please select a date and time."))

    if not contact_name:
        frappe.throw(_("Please enter your name."))

    if not client_name:
        frappe.throw(_("Please enter the young person's name."))

    if not contact_mobile and not contact_email:
        frappe.throw(_("Please enter a mobile number or email address so we can reach you."))

    # Re-check against live availability right before writing anything -
    # closes most of the gap between the visitor loading the slot list and
    # clicking submit a minute later.
    if time not in _compute_available_slots(coach, date):
        frappe.throw(_("Sorry, that time is no longer available. Please choose another slot."))

    coach_user = _get_coach_user(coach)
    if not coach_user:
        frappe.throw(_("This coach is not available for online booking right now."))

    start_dt = get_datetime(f"{date} {time}:00")
    end_dt = add_to_date(start_dt, minutes=INITIAL_CONSULTATION_DURATION_MINUTES)

    # Final guard immediately before insert, to shrink the race window from
    # "load slots -> submit" down to just this one query -> insert gap.
    still_free = not frappe.get_all(
        "Event",
        filters=[
            ["owner", "=", coach_user],
            ["starts_on", "<", end_dt],
            ["ends_on", ">", start_dt],
        ],
        limit_page_length=1,
        ignore_permissions=True,
    )

    if not still_free:
        frappe.throw(_("Sorry, that time was just booked by someone else. Please choose another slot."))

    from dashboard.api.shared.leads import LEAD_DOCTYPE
    from dashboard.api.shared.calendar import _set_session_type, _event_has_field

    lead = frappe.new_doc(LEAD_DOCTYPE)
    lead.status = "New"
    lead.source = "Public Booking"
    lead.coach = coach
    lead.contact_name = contact_name
    lead.contact_email = contact_email
    lead.contact_mobile = contact_mobile
    lead.client_name = client_name
    lead.enquiry_reason = enquiry_reason
    lead.consent_given = 1
    lead.insert(ignore_permissions=True)

    event = frappe.new_doc("Event")
    event.owner = coach_user
    event.subject = f"{contact_name} - {INITIAL_CONSULTATION_LABEL}"
    event.starts_on = start_dt
    event.ends_on = end_dt

    if _event_has_field("event_type"):
        event.event_type = "Private"

    _set_session_type(event, INITIAL_CONSULTATION_LABEL)

    if _event_has_field("custom_billing_type"):
        event.custom_billing_type = "Non-Billable"

    if _event_has_field("custom_appointment_status"):
        event.custom_appointment_status = "Scheduled"
    elif _event_has_field("status"):
        event.status = "Open"

    if _event_has_field("custom_client_lead"):
        event.custom_client_lead = lead.name

    description_lines = [f"Booked online via public profile."]
    if contact_mobile:
        description_lines.append(f"Phone: {contact_mobile}")
    if enquiry_reason:
        description_lines.append(enquiry_reason)

    if _event_has_field("description"):
        event.description = "\n\n".join(description_lines)

    event.insert(ignore_permissions=True)

    lead.event = event.name
    lead.save(ignore_permissions=True)
    frappe.db.commit()

    create_trk_notification(
        recipient_user=coach_user,
        notification_type="New Public Booking",
        message=f"{contact_name} booked an Initial Consultation for {date} at {time} via your public profile.",
        priority="High",
        reference_doctype=LEAD_DOCTYPE,
        reference_name=lead.name,
    )

    return {"ok": True}
