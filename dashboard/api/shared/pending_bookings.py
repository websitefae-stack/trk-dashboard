"""
Fallback queue for appointment bookings that hit MySQL's naming-series lock
contention even after the quick in-request retries in create_booking().

Rather than make a coach wait out a long lock wait, or fail their booking
outright, while something else briefly holds that shared row, the request
is handed off here: the booking's already-validated parameters (validation
has already happened by the time this is reached - the lock timeout only
ever occurs at the actual Event insert) are stored in a Pending Booking
record. Pending Booking uses hash-based naming specifically so creating one
never contends for the same naming-series row that's the whole problem. A
background job then keeps retrying the real Event creation for as long as
it takes, and the coach sees the booking in their calendar immediately via
the preview data stored alongside it.
"""

import json
import time

import frappe
from frappe import _
from frappe.utils import add_to_date, cint, get_datetime

from dashboard.api.shared.calendar import (
    SESSION_WORKER_DASHBOARD,
    _normalise_dashboard_type,
    _get_context_for_dashboard,
    _get_client_display_name,
    _create_booking_impl,
    compute_occurrence_window,
    _is_lock_wait_timeout_error,
    _capture_lock_contention_diagnostics,
)

QUEUE_LOCK_TIMEOUT_SECONDS = 20
QUEUE_MAX_ATTEMPTS = 8
STUCK_SWEEP_MINUTES = 10


def _compute_preview_windows(kwargs):
    appointment_type = kwargs.get("appointment_type") or "Therapy Session"

    if appointment_type == "Holiday":
        from_date = kwargs.get("from_date")
        to_date = kwargs.get("to_date")
        if not from_date or not to_date:
            return []
        return [{"start": f"{from_date} 00:00:00", "end": f"{to_date} 23:59:00"}]

    booking_date = kwargs.get("booking_date")
    booking_time = kwargs.get("booking_time")
    if not booking_date or not booking_time:
        return []

    try:
        duration_minutes = int(kwargs.get("duration_minutes") or 45)
    except Exception:
        duration_minutes = 45
    if duration_minutes <= 0:
        duration_minutes = 45

    start_dt = get_datetime(f"{booking_date} {booking_time}:00")
    end_dt = add_to_date(start_dt, minutes=duration_minutes)

    repeat_count = 1
    if appointment_type == "Therapy Session" and cint(kwargs.get("recurring")):
        try:
            repeat_count = int(kwargs.get("recurring_count") or 1)
        except Exception:
            repeat_count = 1
        if repeat_count not in (1, 4, 12):
            repeat_count = 1

    occurrence_overrides = kwargs.get("occurrence_overrides") or []
    if isinstance(occurrence_overrides, str):
        try:
            occurrence_overrides = json.loads(occurrence_overrides)
        except Exception:
            occurrence_overrides = []

    recurring_frequency = kwargs.get("recurring_frequency")

    windows = []
    for index in range(repeat_count):
        occ_start, occ_end = compute_occurrence_window(
            index, start_dt, end_dt, recurring_frequency, duration_minutes, occurrence_overrides
        )
        windows.append({"start": occ_start.isoformat(), "end": occ_end.isoformat()})

    return windows


def _compute_preview_subject(kwargs):
    appointment_type = kwargs.get("appointment_type") or "Therapy Session"
    client = kwargs.get("client")

    if client:
        client_label = kwargs.get("client_name") or _get_client_display_name(client)
        return f"{client_label} - {appointment_type}"

    if appointment_type == "Initial Consultation":
        return f"{kwargs.get('lead_name') or 'New enquiry'} - Initial Consultation"

    if kwargs.get("item_name"):
        return f"{kwargs.get('item_name')} - {appointment_type}"

    return appointment_type


def _windows_overlap(a_start, a_end, b_start, b_end):
    return a_start < b_end and a_end > b_start


def _pending_conflict(dashboard_type, context, windows, exclude_name=None):
    if not windows:
        return None

    filters = {"status": ["in", ["Pending", "Processing"]]}

    if dashboard_type == SESSION_WORKER_DASHBOARD:
        worker_name = (context.get("worker_name") or "").strip()
        if not worker_name:
            return None
        filters["worker_filter_name"] = worker_name
    else:
        filters["view_as_user"] = context.get("view_as_user") or frappe.session.user

    candidates = frappe.get_all(
        "Pending Booking",
        filters=filters,
        fields=["name", "preview_subject", "preview_windows_json"],
        ignore_permissions=True,
    )

    for candidate in candidates:
        if exclude_name and candidate.name == exclude_name:
            continue

        try:
            candidate_windows = json.loads(candidate.preview_windows_json or "[]")
        except Exception:
            candidate_windows = []

        for candidate_window in candidate_windows:
            candidate_start = get_datetime(candidate_window.get("start"))
            candidate_end = get_datetime(candidate_window.get("end"))

            for window in windows:
                window_start = get_datetime(window.get("start"))
                window_end = get_datetime(window.get("end"))

                if _windows_overlap(candidate_start, candidate_end, window_start, window_end):
                    return candidate

    return None


def queue_booking(kwargs, dashboard_type=None):
    """
    Store an already-validated booking request for background processing,
    after confirming it doesn't clash with anything else already queued for
    the same coach/worker.
    """
    dashboard_type = _normalise_dashboard_type(dashboard_type)
    context = _get_context_for_dashboard(dashboard_type)

    windows = _compute_preview_windows(kwargs)

    conflict = _pending_conflict(dashboard_type, context, windows)
    if conflict:
        frappe.throw(_(
            "This calendar already has another booking still being saved at an "
            "overlapping time ({0}). Please wait a moment and try again."
        ).format(conflict.get("preview_subject") or conflict.get("name")))

    pending = frappe.new_doc("Pending Booking")
    pending.status = "Pending"
    pending.dashboard_type = dashboard_type
    pending.view_as_user = context.get("view_as_user") or frappe.session.user
    pending.worker_filter_name = (context.get("worker_name") or "").strip()
    pending.preview_subject = _compute_preview_subject(kwargs)
    pending.preview_windows_json = json.dumps(windows)
    pending.payload_json = json.dumps(kwargs)
    pending.attempts = 0
    pending.insert(ignore_permissions=True)

    frappe.enqueue(
        "dashboard.api.shared.pending_bookings.process_pending_booking",
        queue="long",
        timeout=900,
        enqueue_after_commit=True,
        pending_booking_name=pending.name,
    )

    return {
        "queued": True,
        "pending_booking": pending.name,
        "name": "",
        "title": pending.preview_subject,
        "count": len(windows),
        "record_url": "",
    }


def process_pending_booking(pending_booking_name):
    if not frappe.db.exists("Pending Booking", pending_booking_name):
        return

    pending = frappe.get_doc("Pending Booking", pending_booking_name)
    if pending.status == "Completed":
        return

    pending.status = "Processing"
    pending.save(ignore_permissions=True)
    frappe.db.commit()

    try:
        kwargs = json.loads(pending.payload_json or "{}")
    except Exception:
        kwargs = {}

    try:
        frappe.db.sql(f"SET SESSION innodb_lock_wait_timeout = {QUEUE_LOCK_TIMEOUT_SECONDS}")
    except Exception:
        pass

    last_error = None

    for attempt in range(1, QUEUE_MAX_ATTEMPTS + 1):
        try:
            result = _create_booking_impl(**kwargs)
        except Exception as e:
            last_error = e
            frappe.db.rollback()
            frappe.local.flags.pop("coach_calendar_sync_scheduled_jobs", None)
            frappe.local.flags.pop("dashboard_recalc_balance_scheduled_jobs", None)

            if not _is_lock_wait_timeout_error(e):
                break

            pending.reload()
            pending.attempts = attempt
            pending.save(ignore_permissions=True)
            frappe.db.commit()

            if attempt < QUEUE_MAX_ATTEMPTS:
                time.sleep(min(2 * attempt, 20))
            continue
        else:
            pending.reload()
            pending.status = "Completed"
            pending.created_event_names = json.dumps([result.get("name")] if result.get("name") else [])
            pending.save(ignore_permissions=True)
            frappe.db.commit()
            return

    error_text = str(last_error) if last_error else "Unknown error"

    pending.reload()
    pending.status = "Failed"
    pending.last_error = error_text[:5000]
    pending.save(ignore_permissions=True)
    frappe.db.commit()

    if last_error is not None and _is_lock_wait_timeout_error(last_error):
        _capture_lock_contention_diagnostics(last_error)

    frappe.log_error(
        f"Pending Booking {pending_booking_name} failed after {QUEUE_MAX_ATTEMPTS} attempts: {error_text}",
        "Pending Booking Failed",
    )


def sweep_stuck_pending_bookings():
    """
    Safety net, run on a schedule: picks up any Pending Booking that never
    got processed (e.g. the worker that would have run it crashed before
    picking up the job) instead of letting it sit there forever.
    """
    cutoff = add_to_date(frappe.utils.now_datetime(), minutes=-STUCK_SWEEP_MINUTES)

    stuck = frappe.get_all(
        "Pending Booking",
        filters=[
            ["status", "in", ["Pending", "Processing"]],
            ["modified", "<", cutoff],
        ],
        pluck="name",
        ignore_permissions=True,
    )

    for name in stuck:
        frappe.enqueue(
            "dashboard.api.shared.pending_bookings.process_pending_booking",
            queue="long",
            timeout=900,
            pending_booking_name=name,
        )


def get_pending_bookings_for_calendar(dashboard_type, context, range_start_date, range_end_date):
    """
    Lightweight preview rows for anything still queued/being retried, so a
    coach sees their booking in the calendar immediately instead of it
    looking like nothing happened while the background job keeps trying.
    Failed bookings are included too (recent ones only) - a booking that
    could never be created must not just silently vanish from view with no
    explanation once the retries run out.
    """
    recent_cutoff = add_to_date(frappe.utils.now_datetime(), hours=-24)
    filters = [
        ["status", "in", ["Pending", "Processing", "Failed"]],
        ["modified", ">", recent_cutoff],
    ]

    if dashboard_type == SESSION_WORKER_DASHBOARD:
        worker_name = (context.get("worker_name") or "").strip()
        if not worker_name:
            return []
        filters.append(["worker_filter_name", "=", worker_name])
    else:
        filters.append(["view_as_user", "=", context.get("view_as_user") or frappe.session.user])

    rows = frappe.get_all(
        "Pending Booking",
        filters=filters,
        fields=["name", "preview_subject", "preview_windows_json", "status", "last_error"],
        ignore_permissions=True,
    )

    range_start = get_datetime(f"{range_start_date} 00:00:00")
    range_end = get_datetime(f"{range_end_date} 23:59:59")

    events = []

    for row in rows:
        try:
            windows = json.loads(row.preview_windows_json or "[]")
        except Exception:
            windows = []

        is_failed = row.status == "Failed"

        for window in windows:
            window_start = get_datetime(window.get("start"))
            window_end = get_datetime(window.get("end"))

            if window_start > range_end or window_end < range_start:
                continue

            events.append({
                "id": row.name,
                "name": row.name,
                "is_failed": 1 if is_failed else 0,
                "last_error": row.last_error if is_failed else "",
                "title": (row.preview_subject or "") + (" - could not be saved" if is_failed else ""),
                "client_display_name": (row.preview_subject or "") + (" - could not be saved" if is_failed else ""),
                "date": window_start.strftime("%Y-%m-%d"),
                "start_time": window_start.strftime("%H:%M"),
                "end_time": window_end.strftime("%H:%M"),
                "type": "Failed" if is_failed else "Saving",
                "ui_status": "Failed" if is_failed else "Pending",
                "is_pending": 1,
            })

    return events
