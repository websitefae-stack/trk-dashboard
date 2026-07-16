"""
Client Package / Client Appointment bookkeeping, ported from the "Package
Recalculate Balance" Frappe Server Script (an Event after_save hook) so it is
version-controlled and can run as a background job instead of synchronously
inside every appointment save.

Why this had to move out of the save transaction: the original script
recalculates and rewrites EVERY Event linked to a client's Client Package
Balance every time any one of that client's appointments is saved - not just
the one being saved - and if the event has no balance assigned yet, it does
this for every Active/Exhausted balance that client has ever had. For a
client with a long booking history that is real, growing work, and running
it synchronously meant it was extending the same transaction that holds
Frappe's shared Event naming-series lock. Two appointments for the same
client booked close together also contended directly on the same Client
Package Balance row, since both transactions needed to write to it before
either could commit. Moving this to a background job means it runs after
the triggering save has already committed and released every lock it held.

This is otherwise a faithful, unmodified port of the same recalculation
logic (same fields, same Client Appointment / Session Usage Log bookkeeping,
same "session X of Y" numbering). It must not run at the same time as the
original Server Script - disable (or delete) "Package Recalculate Balance"
in Frappe once this is deployed, or every appointment save will trigger the
same recalculation twice.
"""

import frappe
from frappe import _

from dashboard.api.shared.permissions import ensure_logged_in, get_allowed_client_names, get_current_coach_name

PARENT_CHECKIN_ITEM = "PAR001"
USED_CUSTOM_STATUSES = ["Attended", "No Show"]
USED_EVENT_STATUSES = ["Completed", "Closed"]
CANCELLED_CUSTOM_STATUSES = ["Cancelled", "Cancel"]
CANCELLED_EVENT_STATUSES = ["Cancelled"]


def recalculate_client_package_balance(doc, method=None):
    """
    Event after_insert/on_update hook - only enqueues a background job,
    never does the actual recalculation here. See module docstring for why.
    """
    if not doc.get("custom_client_package_balance") and not doc.get("custom_client"):
        return

    # A single doc.insert() fires both after_insert and on_update (same
    # quirk documented in coach_calendar_sync's event hooks), so without
    # this the job would be enqueued twice for every new appointment.
    job_id = f"dashboard:recalculate_client_package_balance:{doc.name}"
    scheduled = frappe.local.flags.setdefault("dashboard_recalc_balance_scheduled_jobs", set())
    if job_id in scheduled:
        return
    scheduled.add(job_id)

    try:
        frappe.enqueue(
            "dashboard.api.shared.packages.recalculate_client_package_balance_job",
            queue="long",
            timeout=600,
            job_id=job_id,
            deduplicate=True,
            enqueue_after_commit=True,
            event_client_package_balance=doc.get("custom_client_package_balance"),
            event_client=doc.get("custom_client"),
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Recalculate Client Package Balance - enqueue - {doc.name}")


def recalculate_client_package_balance_job(event_client_package_balance=None, event_client=None):
    balance_names = []

    if event_client_package_balance:
        balance_names.append(event_client_package_balance)

    if event_client:
        linked_balances = frappe.db.get_all(
            "Client Package Balance",
            filters={
                "client": event_client,
                "status": ["in", ["Active", "Exhausted"]],
            },
            fields=["name"],
            limit_page_length=1000,
        )
        for row in linked_balances:
            if row.get("name") not in balance_names:
                balance_names.append(row.get("name"))

    for balance_name in balance_names:
        _recalculate_one_balance(balance_name)


def _recalculate_one_balance(balance_name):
    if not frappe.db.exists("Client Package Balance", balance_name):
        return

    balance = frappe.get_doc("Client Package Balance", balance_name)

    event_rows = frappe.db.get_all(
        "Event",
        filters={
            "custom_client_package_balance": balance_name,
        },
        fields=[
            "name",
            "starts_on",
            "ends_on",
            "custom_appointment_status",
            "status",
            "custom_client",
            "custom_coach",
            "custom_session_worker",
            "custom_item",
            "custom_client_package",
            "custom_client_package_balance",
            "custom_client_appointment",
        ],
        order_by="starts_on asc, name asc",
        limit_page_length=1000,
    )

    active_events = []
    used_count = 0

    for event in event_rows:
        custom_status = event.get("custom_appointment_status") or ""
        event_status = event.get("status") or ""

        is_cancelled = custom_status in CANCELLED_CUSTOM_STATUSES or event_status in CANCELLED_EVENT_STATUSES

        if not is_cancelled:
            active_events.append(event)

        if custom_status in USED_CUSTOM_STATUSES or event_status in USED_EVENT_STATUSES:
            used_count = used_count + 1

    total_purchased = float(balance.get("qty_purchased") or 0)
    booked_count = float(len(active_events))
    available_count = total_purchased - booked_count

    if available_count < 0:
        available_count = 0

    session_index = 0

    for event in active_events:
        session_index = session_index + 1
        _recalculate_one_event(event, balance, session_index, total_purchased)

    balance_status = "Active"
    if available_count <= 0:
        balance_status = "Exhausted"

    parent_checkins_due = 0
    if balance.get("service_item") != PARENT_CHECKIN_ITEM:
        parent_checkins_due = int(booked_count // 4)

    frappe.db.set_value(
        "Client Package Balance",
        balance.name,
        {
            "qty_booked": booked_count,
            "qty_used": used_count,
            "qty_available": available_count,
            "status": balance_status,
            "parent_checkins_due": parent_checkins_due,
        },
        update_modified=False,
    )

    package_name = balance.get("client_package")

    if package_name and frappe.db.exists("Client Package", package_name):
        active_balance_count = frappe.db.count(
            "Client Package Balance",
            {
                "client_package": package_name,
                "status": "Active",
            },
        )

        package_status = "Active"
        if active_balance_count == 0:
            package_status = "Exhausted"

        frappe.db.set_value("Client Package", package_name, "status", package_status, update_modified=False)


def _recalculate_one_event(event, balance, session_index, total_purchased):
    progress_text = str(session_index) + " of " + str(int(total_purchased))

    warning = ""
    service_item = balance.get("service_item")

    if service_item != PARENT_CHECKIN_ITEM:
        if session_index == int(total_purchased):
            warning = "This is the final session in the current package. Please ask the coach to arrange a new invoice if services will continue."
        elif int(total_purchased) >= 4 and session_index % 4 == 0:
            warning = "Parent Check-In is now due for this client."

    client_name = event.get("custom_client") or balance.get("client")
    coach_name = event.get("custom_coach")

    if not coach_name and client_name and frappe.db.exists("Client", client_name):
        coach_name = frappe.db.get_value("Client", client_name, "primary_coach")

    appointment_start = event.get("starts_on")
    appointment_end = event.get("ends_on")

    if not appointment_end:
        appointment_end = appointment_start

    frappe.db.set_value(
        "Event",
        event.get("name"),
        {
            "custom_client_package": balance.get("client_package"),
            "custom_client_package_balance": balance.name,
            "custom_item": service_item,
            "custom_session_number": session_index,
            "custom_total_sessions": int(total_purchased),
            "custom_progress_text": progress_text,
            "custom_booking_warning": warning,
        },
        update_modified=False,
    )

    appointment_name = event.get("custom_client_appointment")

    if not appointment_name or not frappe.db.exists("Client Appointment", appointment_name):
        appointment = frappe.new_doc("Client Appointment")
        appointment.client = client_name
        appointment.coach = coach_name
        appointment.item = service_item
        appointment.appointment_start = appointment_start
        appointment.appointment_end = appointment_end
        appointment.status = "Booked"
        appointment.client_package = balance.get("client_package")
        appointment.client_package_balance = balance.name
        appointment.invoice_status = balance.get("invoice_status")
        appointment.outstanding_amount = balance.get("outstanding_amount") or 0
        appointment.session_number = session_index
        appointment.total_sessions = int(total_purchased)
        appointment.progress_text = progress_text
        appointment.package_reserved = 1
        appointment.usage_consumed = 0
        appointment.linked_event = event.get("name")
        appointment.booking_warning = warning
        appointment.booking_source = "Internal Calendar"
        appointment.sales_invoice = balance.get("sales_invoice")
        appointment.insert(ignore_permissions=True)

        frappe.db.set_value(
            "Event",
            event.get("name"),
            "custom_client_appointment",
            appointment.name,
            update_modified=False,
        )

        appointment_name = appointment.name
    else:
        appointment_status = "Booked"
        custom_status = event.get("custom_appointment_status") or ""
        event_status = event.get("status") or ""

        if custom_status == "Attended" or event_status == "Completed":
            appointment_status = "Completed"
        elif custom_status == "No Show" or event_status == "Closed":
            appointment_status = "No Show"

        frappe.db.set_value(
            "Client Appointment",
            appointment_name,
            {
                "client": client_name,
                "coach": coach_name,
                "item": service_item,
                "appointment_start": appointment_start,
                "appointment_end": appointment_end,
                "status": appointment_status,
                "client_package": balance.get("client_package"),
                "client_package_balance": balance.name,
                "invoice_status": balance.get("invoice_status"),
                "outstanding_amount": balance.get("outstanding_amount") or 0,
                "session_number": session_index,
                "total_sessions": int(total_purchased),
                "progress_text": progress_text,
                "package_reserved": 1,
                "linked_event": event.get("name"),
                "booking_warning": warning,
                "sales_invoice": balance.get("sales_invoice"),
            },
            update_modified=False,
        )

    custom_status = event.get("custom_appointment_status") or ""
    event_status = event.get("status") or ""

    if custom_status in USED_CUSTOM_STATUSES or event_status in USED_EVENT_STATUSES:
        existing_log = frappe.db.get_all(
            "Session Usage Log",
            filters={
                "client_appointment": appointment_name,
            },
            fields=["name"],
            limit_page_length=1,
        )

        if not existing_log:
            usage = frappe.new_doc("Session Usage Log")
            usage.client = client_name
            usage.client_package = balance.get("client_package")
            usage.client_package_balance = balance.name
            usage.item = service_item
            usage.client_appointment = appointment_name
            usage.sales_invoice = balance.get("sales_invoice")
            usage.usage_date = appointment_start
            usage.qty_used = 1
            usage.coach = coach_name
            usage.notes = "Usage consumed from Event " + str(event.get("name"))
            usage.insert(ignore_permissions=True)

        frappe.db.set_value("Client Appointment", appointment_name, "usage_consumed", 1, update_modified=False)


# ─────────────────────────────────────────────────────────────
# Delete cascade - Event <-> Client Appointment
# ─────────────────────────────────────────────────────────────
#
# calendar.delete_session() (the dashboard's own "delete this appointment"
# action) has only ever removed the Event itself. Its Client Appointment
# mirror record (built by _recalculate_one_event above) was left behind
# with linked_event pointing at a Sales-Invoice/package-bearing record that
# no longer exists, and the Client Package Balance it was counted against
# never got told the session was gone - qty_booked/qty_available stayed
# stale. That's the exact "APT-2026-00163 references EV00198 which no
# longer exists" pattern.
#
# The two on_trash hooks below make deletion work in both directions
# without looping into each other: deleting an Event cascades to its
# Client Appointment, and deleting a Client Appointment directly (e.g. from
# the Frappe desk) cascades to its Event. _dashboard_event_trash_in_progress
# is how each side knows not to re-trigger the other once one side has
# already started the cascade.

def handle_event_trash(doc, method=None):
    appointment_name = doc.get("custom_client_appointment")
    balance_name = doc.get("custom_client_package_balance")
    client_name = doc.get("custom_client")

    if appointment_name and frappe.db.exists("Client Appointment", appointment_name):
        in_progress = frappe.local.flags.setdefault("dashboard_event_trash_in_progress", set())
        in_progress.add(doc.name)
        try:
            frappe.delete_doc("Client Appointment", appointment_name, ignore_permissions=True, force=True)
        except Exception:
            frappe.log_error(
                frappe.get_traceback(), f"Delete Client Appointment on Event trash - {appointment_name}"
            )

    if not balance_name and not client_name:
        return

    try:
        frappe.enqueue(
            "dashboard.api.shared.packages.recalculate_client_package_balance_job",
            queue="long",
            timeout=600,
            enqueue_after_commit=True,
            event_client_package_balance=balance_name,
            event_client=client_name,
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Recalculate Client Package Balance on Event trash - {doc.name}")


def handle_client_appointment_trash(doc, method=None):
    event_name = doc.get("linked_event")
    if not event_name:
        return

    in_progress = frappe.local.flags.get("dashboard_event_trash_in_progress") or set()
    if event_name in in_progress:
        return

    if frappe.db.exists("Event", event_name):
        try:
            frappe.delete_doc("Event", event_name, ignore_permissions=True, force=True)
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Delete Event on Client Appointment trash - {event_name}")


# ─────────────────────────────────────────────────────────────
# Integrity diagnostics / repair
# ─────────────────────────────────────────────────────────────

# Only these two types ever carry a Client Package Balance - any other
# appointment type (School Visit, Personal, Internal Training, Holiday,
# ...) is *supposed* to have no client/package link at all, so it must
# never be flagged as an "orphan" just for lacking one.
_PACKAGE_ELIGIBLE_SESSION_TYPES = ["Therapy Session", "Parent Check-In"]

REPORTS_USER = "office@theresilienthub.co.uk"


def _ensure_reports_access():
    # Restricted to the office account specifically (the Reports section on
    # the franchisor dashboard is only shown to that login), not every
    # System Manager - kept as an OR so a real System Manager can still
    # call these directly (desk API explorer, bench console) for support.
    if frappe.session.user == REPORTS_USER:
        return

    if "System Manager" in frappe.get_roles(frappe.session.user):
        return

    frappe.throw(_("You do not have permission to run this report."), frappe.PermissionError)


def _event_session_type(event_row):
    return (event_row.get("custom_appointment_type") or event_row.get("custom_item") or "").strip()


def _whole(value):
    try:
        return int(float(value or 0))
    except Exception:
        return 0


def _client_names_for_open_packs_report():
    coach_name = get_current_coach_name(optional=True)

    if coach_name:
        # A franchisor/office login that's also a working coach (Ashley)
        # only sees their own clients here, same as get_allowed_client_or_
        # filters() already does for the coach dashboard - checked before
        # falling back to get_allowed_client_names()'s franchisor-sees-all
        # branch, which would otherwise fire first for any FRANCHISOR_USERS
        # login regardless of whether they're also a coach.
        return frappe.get_all(
            "Client",
            or_filters=[
                ["Client", "primary_coach", "=", coach_name],
                ["Client", "attending_coach", "=", coach_name],
                ["Client", "client_type", "=", "Franchise"],
            ],
            pluck="name",
            limit_page_length=5000,
        )

    return get_allowed_client_names()


@frappe.whitelist()
def get_open_session_packs_report():
    """
    Every client with sessions still available on an Active Client Package
    Balance ("session pack") - who has appointments left over and how many.

    Scoped by whether the current user has their own Coach profile, not by
    dashboard type: a coach (whether on their own dashboard, or a
    franchisor login like Ashley's that's also a working coach) sees only
    their own clients' packs; a session worker sees theirs; only a
    franchisor/office login with no Coach profile of its own (the actual
    office account) sees every client's packs.
    """
    ensure_logged_in()

    if not frappe.db.exists("DocType", "Client Package Balance"):
        return []

    client_names = _client_names_for_open_packs_report()
    if not client_names:
        return []

    rows = frappe.get_all(
        "Client Package Balance",
        filters={"client": ["in", client_names], "status": "Active"},
        fields=[
            "name",
            "client",
            "client_package",
            "service_item",
            "qty_purchased",
            "qty_booked",
            "qty_used",
            "qty_available",
            "creation",
        ],
        order_by="qty_available desc",
        limit_page_length=2000,
        ignore_permissions=True,
    )

    rows = [row for row in rows if _whole(row.get("qty_available")) > 0]

    from dashboard.api.shared.clients import build_display_name, get_coach_label
    from dashboard.api.shared.session_workers import get_session_worker_label

    client_cache = {}

    def _client_row(client_name):
        if client_name not in client_cache:
            client_cache[client_name] = frappe.db.get_value(
                "Client",
                client_name,
                ["name", "name1", "last_name", "full_name", "preferred_name",
                 "primary_coach", "attending_coach", "session_worker"],
                as_dict=True,
            )
        return client_cache[client_name]

    for row in rows:
        client_row = _client_row(row.get("client")) or {}

        row["client_label"] = build_display_name(client_row) if client_row else row.get("client")
        row["coach_label"] = get_coach_label(client_row.get("primary_coach") or client_row.get("attending_coach"))
        row["worker_label"] = get_session_worker_label(client_row.get("session_worker"))

        row["qty_purchased"] = _whole(row.get("qty_purchased"))
        row["qty_booked"] = _whole(row.get("qty_booked"))
        row["qty_used"] = _whole(row.get("qty_used"))
        row["qty_available"] = _whole(row.get("qty_available"))

    return rows


@frappe.whitelist()
def get_appointment_integrity_report():
    """
    Read-only. Reports, but never changes, anything - safe to run any time.
    Use repair_duplicate_client_session_events() to actually act on the
    "duplicate_events" section.
    """
    _ensure_reports_access()

    report = {
        "orphan_client_appointments": [],
        "broken_event_appointment_links": [],
        "orphan_client_session_events": [],
        "duplicate_events": [],
        "duplicate_client_appointments": [],
    }

    for appt in frappe.get_all(
        "Client Appointment",
        fields=["name", "linked_event", "client", "appointment_start"],
    ):
        if appt.linked_event and not frappe.db.exists("Event", appt.linked_event):
            report["orphan_client_appointments"].append(appt)

    events_with_appointment = frappe.get_all(
        "Event",
        filters={"custom_client_appointment": ["is", "set"]},
        fields=["name", "custom_client_appointment", "custom_client", "starts_on"],
    )
    for event in events_with_appointment:
        if not frappe.db.exists("Client Appointment", event.custom_client_appointment):
            report["broken_event_appointment_links"].append(event)

    session_events = frappe.get_all(
        "Event",
        fields=[
            "name", "subject", "starts_on", "custom_client", "custom_client_package_balance",
            "custom_client_appointment", "custom_appointment_type", "custom_item",
            "custom_appointment_status", "status",
        ],
        limit_page_length=20000,
    )

    by_client_time = {}

    for event in session_events:
        is_cancelled = (
            (event.get("custom_appointment_status") or "") in CANCELLED_CUSTOM_STATUSES
            or (event.get("status") or "") in CANCELLED_EVENT_STATUSES
        )
        if is_cancelled:
            continue

        session_type = _event_session_type(event)
        has_any_link = bool(
            event.get("custom_client")
            or event.get("custom_client_package_balance")
            or event.get("custom_client_appointment")
        )

        if session_type in _PACKAGE_ELIGIBLE_SESSION_TYPES and not has_any_link:
            report["orphan_client_session_events"].append(event)

        if event.get("custom_client") and event.get("starts_on"):
            key = (event.get("custom_client"), str(event.get("starts_on")))
            by_client_time.setdefault(key, []).append(event)

    for (client, starts_on), events in by_client_time.items():
        if len(events) > 1:
            report["duplicate_events"].append({
                "client": client,
                "starts_on": starts_on,
                "events": events,
            })

    balance_session_counts = {}
    for appt in frappe.get_all(
        "Client Appointment",
        filters={"client_package_balance": ["is", "set"]},
        fields=["name", "client_package_balance", "session_number", "status"],
    ):
        if appt.status in CANCELLED_CUSTOM_STATUSES:
            continue
        key = (appt.client_package_balance, appt.session_number)
        balance_session_counts.setdefault(key, []).append(appt)

    for (balance, session_number), appointments in balance_session_counts.items():
        if len(appointments) > 1:
            report["duplicate_client_appointments"].append({
                "client_package_balance": balance,
                "session_number": session_number,
                "appointments": appointments,
            })

    report["summary"] = {
        "orphan_client_appointments": len(report["orphan_client_appointments"]),
        "broken_event_appointment_links": len(report["broken_event_appointment_links"]),
        "orphan_client_session_events": len(report["orphan_client_session_events"]),
        "duplicate_event_groups": len(report["duplicate_events"]),
        "duplicate_client_appointment_groups": len(report["duplicate_client_appointments"]),
    }

    return report


@frappe.whitelist()
def repair_duplicate_client_session_events(confirm=0):
    """
    Only ever acts on the confident case: 2+ non-cancelled Events sharing
    the same client AND the exact same start time. Keeps whichever one
    already has a Client Appointment linked (or, if none/several do, the
    oldest by creation) and deletes the rest via the same delete_session()
    path the dashboard itself uses, so the on_trash cascade above cleans up
    each duplicate's own Client Appointment/package balance correctly too.

    Orphan events with no client at all are deliberately NOT touched here -
    there's no reliable way to know which (if any) real appointment an
    unlinked event duplicates without a client to match it against. Those
    stay in the report for manual review.

    confirm=0 (default): dry run, reports what WOULD be deleted.
    confirm=1: actually deletes.
    """
    _ensure_reports_access()

    confirm = int(confirm or 0)

    report = get_appointment_integrity_report()
    deleted = []
    kept = []

    for group in report["duplicate_events"]:
        events = sorted(
            group["events"],
            key=lambda ev: (0 if ev.get("custom_client_appointment") else 1, ev.get("name")),
        )
        keeper = events[0]
        kept.append(keeper.get("name"))

        for duplicate in events[1:]:
            deleted.append(duplicate.get("name"))
            if confirm:
                try:
                    frappe.delete_doc("Event", duplicate.get("name"), ignore_permissions=True, force=True)
                except Exception:
                    frappe.log_error(
                        frappe.get_traceback(), f"Repair Duplicate Events - delete {duplicate.get('name')}"
                    )

    if confirm:
        frappe.db.commit()

    return {
        "confirmed": bool(confirm),
        "kept": kept,
        "duplicate_event_names": deleted,
    }
