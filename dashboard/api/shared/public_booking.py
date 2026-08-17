"""
Guest-facing (no login) booking for the appointment types that are meant
to be publicly bookable from a coach's profile page (resilient_domains).
Deliberately self-contained rather than reusing calendar.create_booking()
- that function assumes a logged-in coach/session-worker session
(_require_logged_in_user()) and carries a lot of internal-dashboard-only
complexity (recurring bookings, additional workers, school/company
billing, travel charges) that doesn't apply here. This only ever creates
a single, non-recurring Event plus its Client Lead, mirroring the shape
calendar.py itself builds for Initial Consultation.

Coach.appointment_types can list appointment types that are staff/coach
-only (Supervision, Parent Check-In) - these are never offered publicly,
everything else (Franchisee Call, Initial Consultation, Podcast
Recording, School Meeting, and anything added later) is fair game.
"""

import calendar as _calendar_module

import frappe
from frappe import _
from frappe.utils import get_datetime, add_to_date, getdate, now_datetime

from dashboard.api.shared.utils import coalesce_str
from dashboard.api.shared.appointment_types import (
    is_publicly_bookable,
    get_duration_minutes,
    get_matching_templates,
)
from dashboard.api.shared.email_templates import render_email, plain_text_to_email_html, BOOKING_CONFIRMATION_TEMPLATE
from dashboard.api.shared.notifications import create_trk_notification

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


def _get_template_names_for_type(appointment_type_label, require_public_bookable=True):
    """
    Case-insensitive "contains" match rather than an exact-name match - a
    template named e.g. "Initial Consultation (Online)" or lowercase
    "initial consultation" still gets picked up on both sides instead of
    the button silently doing nothing. Never returns a template that isn't
    flagged for public booking (see appointment_types.is_publicly_bookable),
    UNLESS require_public_bookable=False - only ever passed by the portal
    self-booking functions further down, which are login-gated and hard-
    restricted to PORTAL_BOOKABLE_TYPES rather than being reachable by a
    guest with an arbitrary appointment_type string.

    Staff-only types like Parent Check-In and Supervision were never
    publicly bookable, so nobody ever needed to create a matching
    Appointment Template record for them - get_matching_templates()
    legitimately returns nothing for them. Coach.appointment_types rows
    still use the plain label as their own appointment_name though, so
    when require_public_bookable=False, the label itself is added as a
    fallback match - the public path never does this, since that gating
    depends entirely on a real Appointment Template's
    custom_public_booking_enabled flag.
    """
    if not appointment_type_label:
        return set()

    if require_public_bookable and not is_publicly_bookable(appointment_type_label):
        return set()

    matches = {row.get("name") for row in get_matching_templates(appointment_type_label)}

    if not require_public_bookable:
        matches.add(appointment_type_label)

    return matches


def _get_coach_windows_for_date(coach, date_str, appointment_type, require_public_bookable=True):
    if not frappe.db.exists("Coach", coach):
        return []

    coach_meta = frappe.get_meta("Coach")
    if not coach_meta.has_field("appointment_types"):
        return []

    template_names = _get_template_names_for_type(appointment_type, require_public_bookable=require_public_bookable)
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


def _compute_available_slots(coach, date_str, appointment_type, require_public_bookable=True, duration_minutes=None):
    windows = _get_coach_windows_for_date(coach, date_str, appointment_type, require_public_bookable=require_public_bookable)
    if not windows:
        return []

    if duration_minutes is None:
        duration_minutes = get_duration_minutes(appointment_type)

    coach_user = _get_coach_user(coach)
    booked = _get_coach_booked_windows(coach_user, date_str)
    now = now_datetime()

    slots = []

    for start_time, end_time in windows:
        window_start = get_datetime(f"{date_str} {start_time}")
        window_end = get_datetime(f"{date_str} {end_time}")
        cursor = window_start

        while True:
            slot_end = add_to_date(cursor, minutes=duration_minutes)
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
def get_available_slots(coach=None, date=None, appointment_type=None):
    coach = coalesce_str("coach", coach)
    date = coalesce_str("date", date)
    appointment_type = coalesce_str("appointment_type", appointment_type)

    if not coach or not date or not appointment_type:
        return []

    try:
        requested = getdate(date)
    except Exception:
        return []

    if requested < getdate(now_datetime()) or (requested - getdate(now_datetime())).days > MAX_DAYS_AHEAD:
        return []

    return _compute_available_slots(coach, date, appointment_type)


def _get_windows_by_weekday(coach, appointment_type, require_public_bookable=True):
    """Same as _get_coach_windows_for_date, but grouped by weekday and
    computed once - used by the month view so it doesn't reload the Coach
    doc once per day of the month."""
    if not frappe.db.exists("Coach", coach):
        return {}

    coach_meta = frappe.get_meta("Coach")
    if not coach_meta.has_field("appointment_types"):
        return {}

    template_names = _get_template_names_for_type(appointment_type, require_public_bookable=require_public_bookable)
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
def get_available_dates(coach=None, year=None, month=None, appointment_type=None):
    """Which dates in the given month have at least one open slot for the
    given appointment type, for greying out empty days in the calendar
    picker."""
    coach = coalesce_str("coach", coach)
    year = coalesce_str("year", year)
    month = coalesce_str("month", month)
    appointment_type = coalesce_str("appointment_type", appointment_type)

    if not coach or not year or not month or not appointment_type:
        return []

    try:
        year = int(year)
        month = int(month)
    except Exception:
        return []

    return _compute_available_dates(coach, year, month, appointment_type)


def _compute_available_dates(coach, year, month, appointment_type, require_public_bookable=True, duration_minutes=None):
    windows_by_weekday = _get_windows_by_weekday(coach, appointment_type, require_public_bookable=require_public_bookable)
    if not any(windows_by_weekday.values()):
        return []

    if duration_minutes is None:
        duration_minutes = get_duration_minutes(appointment_type)

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
                slot_end = add_to_date(cursor, minutes=duration_minutes)
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


# ─────────────────────────────────────────────────────────────
# Client portal self-booking (Parent Check-In only)
# ─────────────────────────────────────────────────────────────
#
# Reuses the exact slot-computation engine above (coach availability
# windows minus existing bookings) but bypasses the is_publicly_bookable
# gate, since Parent Check-In is deliberately excluded from the *public*
# guest-facing booking page while still needing to be self-bookable by an
# existing, logged-in client from their own client_portal. Every function
# here requires login (no allow_guest) and hard-restricts appointment_type
# to PORTAL_BOOKABLE_TYPES, so this "skip the public gate" path can never
# be used to fetch availability or book other staff-only types
# (Supervision etc.) by passing a different appointment_type string.
# client_portal reaches these via a guarded frappe.get_attr lookup rather
# than a hard import, same as it does for create_trk_notification - see
# client_portal/api/appointments.py.

PORTAL_BOOKABLE_TYPES = {"Parent Check-In"}
PARENT_CHECKIN_ITEM_CODE = "PAR001"
PARENT_CHECKIN_DURATION_MINUTES = 30


def _ensure_logged_in_portal_user():
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required."), frappe.PermissionError)


def _ensure_portal_bookable_type(appointment_type):
    if appointment_type not in PORTAL_BOOKABLE_TYPES:
        frappe.throw(_("This appointment type cannot be self-booked from the client portal."))


@frappe.whitelist()
def get_portal_slots(coach=None, date=None, appointment_type=None):
    _ensure_logged_in_portal_user()

    coach = coalesce_str("coach", coach)
    date = coalesce_str("date", date)
    appointment_type = coalesce_str("appointment_type", appointment_type)

    _ensure_portal_bookable_type(appointment_type)

    if not coach or not date:
        return []

    try:
        requested = getdate(date)
    except Exception:
        return []

    if requested < getdate(now_datetime()) or (requested - getdate(now_datetime())).days > MAX_DAYS_AHEAD:
        return []

    return _compute_available_slots(
        coach, date, appointment_type,
        require_public_bookable=False,
        duration_minutes=PARENT_CHECKIN_DURATION_MINUTES,
    )


@frappe.whitelist()
def get_portal_dates(coach=None, year=None, month=None, appointment_type=None):
    _ensure_logged_in_portal_user()

    coach = coalesce_str("coach", coach)
    year = coalesce_str("year", year)
    month = coalesce_str("month", month)
    appointment_type = coalesce_str("appointment_type", appointment_type)

    _ensure_portal_bookable_type(appointment_type)

    if not coach or not year or not month:
        return []

    try:
        year = int(year)
        month = int(month)
    except Exception:
        return []

    return _compute_available_dates(
        coach, year, month, appointment_type,
        require_public_bookable=False,
        duration_minutes=PARENT_CHECKIN_DURATION_MINUTES,
    )


def _find_parent_checkin_balance(client):
    if not frappe.db.exists("DocType", "Client Package Balance"):
        return None

    rows = frappe.get_all(
        "Client Package Balance",
        filters={
            "client": client,
            "service_item": PARENT_CHECKIN_ITEM_CODE,
            "status": "Active",
        },
        fields=["name", "qty_available"],
        order_by="creation asc",
        limit_page_length=50,
    )

    for row in rows:
        try:
            if float(row.get("qty_available") or 0) > 0:
                return row.get("name")
        except Exception:
            continue

    return None


@frappe.whitelist()
def create_portal_booking(client=None, coach=None, date=None, time=None, appointment_type=None):
    """
    Books a Parent Check-In directly onto the calendar for an existing
    client, consuming one session from their Parent Check-In package
    balance - the client-portal equivalent of submit_public_booking()
    above, but for an existing Client rather than a new Lead, and gated on
    login + a real, available session pack rather than being guest-facing.
    Callers are expected to have already checked the requesting user has
    can_book_appointments on this client (see client_portal.api.
    appointments.book_parent_checkin) - this function still re-derives the
    coach from the Client record and re-validates the slot itself rather
    than trusting either from the caller.
    """
    _ensure_logged_in_portal_user()

    client = coalesce_str("client", client)
    coach = coalesce_str("coach", coach)
    date = coalesce_str("date", date)
    time = coalesce_str("time", time)
    appointment_type = coalesce_str("appointment_type", appointment_type)

    _ensure_portal_bookable_type(appointment_type)

    if not client or not frappe.db.exists("Client", client):
        frappe.throw(_("Client not found."))

    actual_coach = frappe.db.get_value("Client", client, "primary_coach")
    if not actual_coach or actual_coach != coach:
        frappe.throw(_("This client's coach does not match."), frappe.PermissionError)

    if not date or not time:
        frappe.throw(_("Please select a date and time."))

    balance_name = _find_parent_checkin_balance(client)
    if not balance_name:
        frappe.throw(_("This client has no available Parent Check-In sessions to book."))

    if time not in _compute_available_slots(
        coach, date, appointment_type,
        require_public_bookable=False,
        duration_minutes=PARENT_CHECKIN_DURATION_MINUTES,
    ):
        frappe.throw(_("Sorry, that time is no longer available. Please choose another slot."))

    coach_user = _get_coach_user(coach)
    if not coach_user:
        frappe.throw(_("This coach is not available for booking right now."))

    start_dt = get_datetime(f"{date} {time}:00")
    end_dt = add_to_date(start_dt, minutes=PARENT_CHECKIN_DURATION_MINUTES)

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

    from dashboard.api.shared.calendar import _set_session_type, _event_has_field

    client_full_name = frappe.db.get_value("Client", client, "full_name") or client

    event = frappe.new_doc("Event")
    event.owner = coach_user
    event.subject = f"{client_full_name} - {appointment_type}"
    event.starts_on = start_dt
    event.ends_on = end_dt

    if _event_has_field("event_type"):
        event.event_type = "Private"

    _set_session_type(event, appointment_type)

    if _event_has_field("custom_client"):
        event.custom_client = client

    if _event_has_field("custom_coach"):
        event.custom_coach = coach

    if _event_has_field("custom_client_package_balance"):
        event.custom_client_package_balance = balance_name

    if _event_has_field("custom_billing_type"):
        event.custom_billing_type = "Non-Billable"

    if _event_has_field("custom_appointment_status"):
        event.custom_appointment_status = "Scheduled"
    elif _event_has_field("status"):
        event.status = "Open"

    if _event_has_field("description"):
        event.description = "Booked by the client via the client portal."

    event.insert(ignore_permissions=True)
    frappe.db.commit()

    # Best-effort side effect only - the booking itself already committed
    # above, so a broken notification config must never make the booking
    # appear to have failed.
    try:
        create_trk_notification(
            recipient_user=coach_user,
            notification_type="Client Request",
            message=f"{client_full_name} booked a Parent Check-In for {date} at {time} via the client portal.",
            priority="Normal",
            reference_doctype="Event",
            reference_name=event.name,
            client=client,
            event=event.name,
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Portal Booking - Coach Notification Failed")

    return {"ok": True, "event": event.name}


@frappe.whitelist(allow_guest=True)
def submit_public_booking(
    coach=None,
    date=None,
    time=None,
    appointment_type=None,
    contact_name=None,
    client_name=None,
    contact_mobile=None,
    contact_email=None,
    enquiry_reason=None,
    location_address=None,
):
    coach = coalesce_str("coach", coach)
    date = coalesce_str("date", date)
    time = coalesce_str("time", time)
    appointment_type = coalesce_str("appointment_type", appointment_type)
    contact_name = coalesce_str("contact_name", contact_name)
    client_name = coalesce_str("client_name", client_name)
    contact_mobile = coalesce_str("contact_mobile", contact_mobile)
    contact_email = coalesce_str("contact_email", contact_email)
    enquiry_reason = coalesce_str("enquiry_reason", enquiry_reason)
    location_address = coalesce_str("location_address", location_address)

    if not coach or not frappe.db.exists("Coach", coach):
        frappe.throw(_("This coach was not found."))

    if not appointment_type or not is_publicly_bookable(appointment_type):
        frappe.throw(_("This appointment type is not available for online booking."))

    if not date or not time:
        frappe.throw(_("Please select a date and time."))

    if not contact_name:
        frappe.throw(_("Please enter your name."))

    if not client_name:
        frappe.throw(_("Please enter the young person's name."))

    if not contact_mobile and not contact_email:
        frappe.throw(_("Please enter a mobile number or email address so we can reach you."))

    duration_minutes = get_duration_minutes(appointment_type)

    # Re-check against live availability right before writing anything -
    # closes most of the gap between the visitor loading the slot list and
    # clicking submit a minute later.
    if time not in _compute_available_slots(coach, date, appointment_type):
        frappe.throw(_("Sorry, that time is no longer available. Please choose another slot."))

    coach_user = _get_coach_user(coach)
    if not coach_user:
        frappe.throw(_("This coach is not available for online booking right now."))

    start_dt = get_datetime(f"{date} {time}:00")
    end_dt = add_to_date(start_dt, minutes=duration_minutes)

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
    lead.appointment_type = appointment_type
    lead.coach = coach
    lead.contact_name = contact_name
    lead.contact_email = contact_email
    lead.contact_mobile = contact_mobile
    lead.client_name = client_name
    lead.enquiry_reason = enquiry_reason
    lead.location_address = location_address
    lead.consent_given = 1
    lead.insert(ignore_permissions=True)

    event = frappe.new_doc("Event")
    event.owner = coach_user
    event.subject = f"{contact_name} - {appointment_type}"
    event.starts_on = start_dt
    event.ends_on = end_dt

    if _event_has_field("event_type"):
        event.event_type = "Private"

    _set_session_type(event, appointment_type)

    if _event_has_field("custom_billing_type"):
        event.custom_billing_type = "Non-Billable"

    if _event_has_field("custom_appointment_status"):
        event.custom_appointment_status = "Scheduled"
    elif _event_has_field("status"):
        event.status = "Open"

    if _event_has_field("custom_client_lead"):
        event.custom_client_lead = lead.name

    if location_address and _event_has_field("location"):
        event.location = location_address

    description_lines = ["Booked online via public profile."]
    if contact_mobile:
        description_lines.append(f"Phone: {contact_mobile}")
    if location_address:
        description_lines.append(f"Location: {location_address}")
    if enquiry_reason:
        description_lines.append(enquiry_reason)

    if _event_has_field("description"):
        event.description = "\n\n".join(description_lines)

    event.insert(ignore_permissions=True)

    lead.event = event.name
    lead.save(ignore_permissions=True)
    frappe.db.commit()

    # Both of these are best-effort side effects, not part of the booking
    # itself (already committed above) - a broken email/notification
    # config must never make the booking appear to have failed.
    try:
        create_trk_notification(
            recipient_user=coach_user,
            notification_type="Client Request",
            message=f"{contact_name} booked {appointment_type} for {date} at {time} via your public profile.",
            priority="High",
            reference_doctype=LEAD_DOCTYPE,
            reference_name=lead.name,
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Public Booking - Coach Notification Failed")

    if contact_email:
        try:
            _send_booking_confirmation_email(
                contact_email=contact_email,
                contact_name=contact_name,
                coach=coach,
                appointment_type=appointment_type,
                date=date,
                time=time,
                location_address=location_address,
            )
        except Exception:
            frappe.log_error(frappe.get_traceback(), "Public Booking - Confirmation Email Failed")

    return {"ok": True}


def _send_booking_confirmation_email(contact_email, contact_name, coach, appointment_type, date, time, location_address):
    coach_display_name = frappe.db.get_value("Coach", coach, "coach_name") or coach
    date_text = get_datetime(f"{date} 00:00:00").strftime("%A %d %B %Y")

    # Values are escaped before going into the Jinja context (rather than
    # relying on template autoescaping) since these strings include
    # visitor-entered free text (contact_name, location_address).
    context = {
        "contact_name": frappe.utils.escape_html(contact_name or ""),
        "appointment_type": frappe.utils.escape_html(appointment_type or ""),
        "coach_name": frappe.utils.escape_html(coach_display_name or ""),
        "date": frappe.utils.escape_html(date_text),
        "time": frappe.utils.escape_html(time or ""),
        "location_address": frappe.utils.escape_html(location_address or ""),
    }

    fallback_message = (
        "Hi {{ contact_name }},\n"
        "\n"
        "Your {{ appointment_type }} with {{ coach_name }} is confirmed:\n"
        "\n"
        "{{ date }} at {{ time }}"
        "{% if location_address %}\n"
        "Location: {{ location_address }}{% endif %}\n"
        "\n"
        "We'll be in touch if anything changes. See you then!"
    )

    subject, message = render_email(
        BOOKING_CONFIRMATION_TEMPLATE,
        context,
        fallback_subject="Your {{ appointment_type }} is confirmed",
        fallback_message=fallback_message,
    )

    # No logged-in session here (this is a public/guest booking flow), so
    # reply_to can't default to frappe.session.user like the dashboard's
    # own send functions do - resolved from the coach this booking is
    # actually with instead, via the same lookup get_available_slots()
    # etc. already use.
    reply_to = _get_coach_user(coach)

    kwargs = {
        "recipients": [contact_email],
        "subject": subject,
        "message": plain_text_to_email_html(message),
        "now": True,
    }

    if reply_to:
        kwargs["reply_to"] = reply_to

    frappe.sendmail(**kwargs)
