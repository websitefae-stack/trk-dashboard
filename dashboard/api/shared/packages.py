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
