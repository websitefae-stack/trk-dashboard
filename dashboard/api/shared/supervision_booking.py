"""
Self-service Supervision booking, staff-to-staff (never client-facing):

- A coach always books Supervision with Ashley specifically - she's the
  only one who supervises coaches today.
- A session worker books Supervision with whichever of their own active
  linked coaches they need to - each supervising coach follows up on
  their own clients with that session worker.

Nobody's supervision times are hardcoded here - both sides reuse the
exact same slot-computation engine as public/portal booking
(public_booking._compute_available_slots/_compute_available_dates,
Coach.appointment_types windows minus existing bookings), so a booking
is only ever offered against whatever Ashley/a coach has actually set up
in their own Availability for a "Supervision" row. Only WHO you're
allowed to book with is fixed by code (Ashley for coaches, your own
linked_coaches for session workers) - WHEN is entirely theirs to
configure, same as every other appointment type.
"""

import frappe
from frappe import _
from frappe.utils import get_datetime, add_to_date, getdate, now_datetime

from dashboard.api.shared.appointment_types import get_duration_minutes
from dashboard.api.shared.notifications import create_trk_notification
from dashboard.api.shared.permissions import (
    ensure_logged_in,
    get_active_session_worker_coaches,
    get_current_coach_name,
    get_current_session_worker_name,
    get_current_user_dashboard_type,
)
from dashboard.api.shared.public_booking import (
    MAX_DAYS_AHEAD,
    _compute_available_slots,
    _get_coach_user,
)
from dashboard.api.shared.utils import coalesce_str

SUPERVISION_TYPE_LABEL = "Supervision"
ASHLEY_EMAIL = "ashley@theresilientkid.co.uk"


def get_ashley_coach_name():
    return (
        frappe.db.get_value("Coach", {"user": ASHLEY_EMAIL}, "name")
        or frappe.db.get_value("Coach", {"coach_email": ASHLEY_EMAIL}, "name")
    )


def get_coach_supervision_target():
    """Called directly from client_details.py's context builder (same
    app, no need for a whitelisted round trip) to decide whether/who to
    show a "Book Supervision" widget for on a Franchise-type client page.
    Returns None if Ashley has no Coach profile on this site, or if the
    current user isn't a coach at all (e.g. franchisor viewing the page).
    """
    if get_current_user_dashboard_type() != "coach":
        return None

    ashley_coach = get_ashley_coach_name()
    if not ashley_coach:
        return None

    # Ashley can't book Supervision with herself.
    if get_current_coach_name(optional=True) == ashley_coach:
        return None

    return {
        "coach": ashley_coach,
        "coach_name": frappe.db.get_value("Coach", ashley_coach, "coach_name") or "Ashley",
    }


def _ensure_requester_can_book_with(coach):
    ensure_logged_in()

    dashboard_type = get_current_user_dashboard_type()

    if dashboard_type == "coach":
        ashley_coach = get_ashley_coach_name()
        if not ashley_coach or coach != ashley_coach:
            frappe.throw(_("Coaches can only book Supervision with Ashley."), frappe.PermissionError)
        return

    if dashboard_type == "session_worker":
        session_worker_name = get_current_session_worker_name(optional=True)
        if not session_worker_name:
            frappe.throw(_("No Session Worker profile is linked to your user."), frappe.PermissionError)

        session_worker = frappe.get_doc("Session Worker", session_worker_name)
        allowed_coaches = get_active_session_worker_coaches(session_worker)

        if coach not in allowed_coaches:
            frappe.throw(_("You can only book Supervision with a coach you're linked to."), frappe.PermissionError)
        return

    frappe.throw(_("You are not allowed to book Supervision."), frappe.PermissionError)


def _get_requester_display_name():
    dashboard_type = get_current_user_dashboard_type()

    if dashboard_type == "coach":
        coach_name = get_current_coach_name(optional=True)
        return frappe.db.get_value("Coach", coach_name, "coach_name") or coach_name or frappe.session.user

    if dashboard_type == "session_worker":
        session_worker_name = get_current_session_worker_name(optional=True)
        return frappe.db.get_value("Session Worker", session_worker_name, "sw_name") or session_worker_name or frappe.session.user

    return frappe.session.user


@frappe.whitelist()
def get_supervision_slots(coach=None, date=None):
    coach = coalesce_str("coach", coach)
    date = coalesce_str("date", date)

    _ensure_requester_can_book_with(coach)

    if not coach or not date:
        return []

    try:
        requested = getdate(date)
    except Exception:
        return []

    if requested < getdate(now_datetime()) or (requested - getdate(now_datetime())).days > MAX_DAYS_AHEAD:
        return []

    return _compute_available_slots(coach, date, SUPERVISION_TYPE_LABEL, require_public_bookable=False)


@frappe.whitelist()
def book_supervision(coach=None, date=None, time=None):
    coach = coalesce_str("coach", coach)
    date = coalesce_str("date", date)
    time = coalesce_str("time", time)

    _ensure_requester_can_book_with(coach)

    if not date or not time:
        frappe.throw(_("Please select a date and time."))

    duration_minutes = get_duration_minutes(SUPERVISION_TYPE_LABEL)

    if time not in _compute_available_slots(coach, date, SUPERVISION_TYPE_LABEL, require_public_bookable=False):
        frappe.throw(_("Sorry, that time is no longer available. Please choose another slot."))

    coach_user = _get_coach_user(coach)
    if not coach_user:
        frappe.throw(_("This coach is not available for booking right now."))

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

    from dashboard.api.shared.calendar import _set_session_type, _event_has_field

    requester_name = _get_requester_display_name()

    event = frappe.new_doc("Event")
    event.owner = coach_user
    event.subject = f"Supervision - {requester_name}"
    event.starts_on = start_dt
    event.ends_on = end_dt

    if _event_has_field("event_type"):
        event.event_type = "Private"

    _set_session_type(event, SUPERVISION_TYPE_LABEL)

    if _event_has_field("custom_coach"):
        event.custom_coach = coach

    if _event_has_field("custom_appointment_status"):
        event.custom_appointment_status = "Scheduled"
    elif _event_has_field("status"):
        event.status = "Open"

    if _event_has_field("description"):
        event.description = f"Supervision booked by {requester_name} via self-service booking."

    event.insert(ignore_permissions=True)
    frappe.db.commit()

    # Best-effort side effect only - the booking itself already committed
    # above, so a broken notification config must never make the booking
    # appear to have failed.
    try:
        create_trk_notification(
            recipient_user=coach_user,
            notification_type="New Supervision Booking",
            message=f"{requester_name} booked Supervision with you for {date} at {time}.",
            priority="Normal",
            reference_doctype="Event",
            reference_name=event.name,
            event=event.name,
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Supervision Booking - Notification Failed")

    return {"ok": True, "event": event.name}
