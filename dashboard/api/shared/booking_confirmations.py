"""
"Send booking confirmation email to client" at booking time (the checkbox
in the booking modal), covering every occurrence created in one booking
action - not the same as the existing single-event
send_booking_confirmation_email() in calendar.py, which is for emailing
one already-booked session on demand.

A Google Meet link is created asynchronously by coach_calendar_sync's push
job, not at booking time - sending immediately for an online session would
almost always go out with no link yet. handle_booking_confirmation_request()
sends immediately when nothing in the batch needs a meet link; otherwise it
marks the batch pending, and the scheduled sweep below
(send_pending_booking_confirmations, wired into hooks.py's 5-minute cron)
sends it once every online occurrence has a link - or after
PENDING_TIMEOUT_MINUTES, whichever comes first, so a booking never goes
completely un-confirmed just because a sync attempt is stuck.

Also owns send_online_session_reminders() - a separate 1-hour-before
reminder for online sessions specifically, confirmed requested live
after the business owner couldn't find any existing reminder feature
anywhere in this codebase (there wasn't one). Every email this module
sends goes through _send_confirmation_email(), which wraps the message
in wrap_branded_email_html() so confirmations, meet-link follow-ups and
reminders are all consistently branded rather than a bare paragraph of
text.
"""

import frappe
from frappe.utils import add_to_date, get_datetime, now_datetime

from dashboard.api.shared.calendar import _event_has_field, _get_client_display_name, _is_online_location
from dashboard.api.shared.email_templates import plain_text_to_email_html, wrap_branded_email_html
from dashboard.api.shared.invoices import _coach_label_from_name, get_client_email_options
from dashboard.api.shared.mail_throttle import send_email

PENDING_TIMEOUT_MINUTES = 10
FOLLOWUP_GIVE_UP_HOURS = 24

# How long before an online session's start time the reminder sweep
# targets, and how wide a net it casts around that mark - wide enough to
# comfortably straddle the 5-minute cron interval (hooks.py) so a run
# that's a few minutes early or late never skips an event entirely, kept
# safe from duplicates by custom_reminder_sent regardless of how many
# sweeps actually see the same event inside that window.
REMINDER_LEAD_MINUTES = 60
REMINDER_WINDOW_MINUTES = 10


def _batch_needs_meet_link(created_events):
    return any(_is_online_location(event.get("location")) for event in created_events)


def _compose_multi_session_message(event_rows, client):
    lines = []

    for row in event_rows:
        start_dt = get_datetime(row.get("starts_on"))
        line = f"- {start_dt.strftime('%A %d %B %Y')} at {start_dt.strftime('%H:%M')}"

        location = row.get("location") or ""
        meet_link = row.get("custom_google_meet_url") or row.get("google_meet_link") or ""
        is_online = _is_online_location(location)

        if location and not is_online:
            line += f", {location}"

        if is_online and meet_link:
            line += f" - here is the Google Meet link for easy access: {meet_link}"
        elif is_online:
            line += " - the online meeting link will follow separately"

        lines.append(line)

    contact_name = _get_client_display_name(client)
    session_word = "session" if len(event_rows) == 1 else "sessions"

    subject = f"Your upcoming {session_word} " + (
        "is confirmed" if len(event_rows) == 1 else "are confirmed"
    )

    message = (
        f"Hi {contact_name},\n\n"
        f"Your upcoming {session_word} "
        + ("is" if len(event_rows) == 1 else "are")
        + " confirmed:\n\n"
        + "\n".join(lines)
        + "\n\nPlease let us know if you have any questions or need to make any changes.\n\n"
        "The Resilient Office"
    )

    return subject, message


def _compose_meet_link_followup_message(event_rows, client):
    """
    Short follow-up for a booking whose confirmation email already went out
    saying "the online meeting link will follow separately" - only ever
    called once the link has actually turned up, so this just delivers on
    that promise instead of leaving the client to wonder.
    """
    lines = []

    for row in event_rows:
        meet_link = row.get("custom_google_meet_url") or row.get("google_meet_link") or ""
        if not meet_link:
            continue

        start_dt = get_datetime(row.get("starts_on"))
        lines.append(f"- {start_dt.strftime('%A %d %B %Y')} at {start_dt.strftime('%H:%M')} - here is the Google Meet link for easy access: {meet_link}")

    if not lines:
        return None, None

    contact_name = _get_client_display_name(client)
    plural = len(lines) > 1

    subject = "Your Google Meet link" + ("s" if plural else "")
    message = (
        f"Hi {contact_name},\n\n"
        "As promised, here's the Google Meet link for your upcoming session"
        + ("s" if plural else "") + ":\n\n"
        + "\n".join(lines)
        + "\n\nThe Resilient Office"
    )

    return subject, message


def _send_confirmation_email(recipient, subject, message, reference_event):
    try:
        send_email(
            recipients=[recipient],
            subject=subject,
            message=wrap_branded_email_html(plain_text_to_email_html(message)),
            reference_doctype="Event",
            reference_name=reference_event,
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Booking Confirmation Email Failed")


def handle_booking_confirmation_request(created_events, client, recipient):
    """
    created_events: the frappe.new_doc("Event") docs just inserted by
    _create_booking_impl for this one booking action (one per recurring
    occurrence). Never raises - a booking must succeed regardless of
    whether its confirmation email can be sent.
    """
    if not created_events or not client or not recipient:
        return

    if not _event_has_field("custom_confirmation_pending"):
        # Site hasn't migrated the patch yet - nothing to do rather than
        # failing the booking over an email feature that isn't set up.
        return

    event_names = [event.name for event in created_events]

    if not _batch_needs_meet_link(created_events):
        event_rows = [
            {"starts_on": event.starts_on, "location": event.get("location") or ""}
            for event in created_events
        ]
        subject, message = _compose_multi_session_message(event_rows, client)
        _send_confirmation_email(recipient, subject, message, event_names[0])
        return

    try:
        frappe.db.set_value(
            "Event",
            event_names[0],
            {
                "custom_confirmation_pending": 1,
                "custom_confirmation_recipient": recipient,
                "custom_confirmation_batch_events": ",".join(event_names),
            },
            update_modified=False,
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Booking Confirmation Pending Flag Failed")


def send_pending_booking_confirmations():
    """
    Scheduled sweep (hooks.py, every 5 minutes) - sends any confirmation
    email that was waiting on a Google Meet link, once every online
    occurrence in its batch has one, or PENDING_TIMEOUT_MINUTES have
    passed since the booking was made (whichever comes first).
    """
    if not _event_has_field("custom_confirmation_pending"):
        return

    leaders = frappe.get_all(
        "Event",
        filters={"custom_confirmation_pending": 1},
        fields=["name", "custom_confirmation_recipient", "custom_confirmation_batch_events", "creation",
                "custom_client"],
    )

    cutoff = add_to_date(now_datetime(), minutes=-PENDING_TIMEOUT_MINUTES)

    for leader in leaders:
        event_names = [n.strip() for n in (leader.custom_confirmation_batch_events or "").split(",") if n.strip()]

        if not event_names or not leader.custom_confirmation_recipient:
            frappe.db.set_value("Event", leader.name, "custom_confirmation_pending", 0, update_modified=False)
            continue

        fields = ["name", "starts_on", "location", "custom_google_meet_url"]
        if _event_has_field("google_meet_link"):
            fields.append("google_meet_link")

        event_rows = frappe.get_all(
            "Event",
            filters={"name": ["in", event_names]},
            fields=fields,
            order_by="starts_on asc",
        )

        if not event_rows:
            frappe.db.set_value("Event", leader.name, "custom_confirmation_pending", 0, update_modified=False)
            continue

        still_waiting = any(
            _is_online_location(row.get("location")) and not (row.get("custom_google_meet_url") or row.get("google_meet_link"))
            for row in event_rows
        )

        if still_waiting and leader.creation > cutoff:
            continue

        subject, message = _compose_multi_session_message(event_rows, leader.custom_client)
        _send_confirmation_email(leader.custom_confirmation_recipient, subject, message, leader.name)

        updates = {"custom_confirmation_pending": 0}

        if still_waiting and _event_has_field("custom_confirmation_link_pending"):
            # Timed out before the Meet link was ready - the email that just
            # went out says "the link will follow separately", so remember
            # to actually send that follow-up once the link exists instead
            # of leaving it an empty promise (see
            # send_pending_meet_link_followups() below).
            updates["custom_confirmation_link_pending"] = 1

        frappe.db.set_value("Event", leader.name, updates, update_modified=False)

    frappe.db.commit()


def send_pending_meet_link_followups():
    """
    Scheduled sweep (hooks.py, every 5 minutes) - for a booking confirmation
    that already went out saying "the link will follow separately" (see
    send_pending_booking_confirmations() above), sends a short follow-up
    once the Google Meet link actually turns up. Gives up silently after
    FOLLOWUP_GIVE_UP_HOURS if it never does - a sync that's been failing
    that long needs a human to look at it, not more emails promising a link
    that isn't coming.
    """
    if not _event_has_field("custom_confirmation_link_pending"):
        return

    leaders = frappe.get_all(
        "Event",
        filters={"custom_confirmation_link_pending": 1},
        fields=["name", "custom_confirmation_recipient", "custom_confirmation_batch_events", "creation",
                "custom_client"],
    )

    give_up_cutoff = add_to_date(now_datetime(), hours=-FOLLOWUP_GIVE_UP_HOURS)

    for leader in leaders:
        event_names = [n.strip() for n in (leader.custom_confirmation_batch_events or "").split(",") if n.strip()]

        if not event_names or not leader.custom_confirmation_recipient:
            frappe.db.set_value("Event", leader.name, "custom_confirmation_link_pending", 0, update_modified=False)
            continue

        fields = ["name", "starts_on", "location", "custom_google_meet_url"]
        if _event_has_field("google_meet_link"):
            fields.append("google_meet_link")

        event_rows = frappe.get_all(
            "Event",
            filters={"name": ["in", event_names]},
            fields=fields,
            order_by="starts_on asc",
        )

        if not event_rows:
            frappe.db.set_value("Event", leader.name, "custom_confirmation_link_pending", 0, update_modified=False)
            continue

        still_waiting = any(
            _is_online_location(row.get("location")) and not (row.get("custom_google_meet_url") or row.get("google_meet_link"))
            for row in event_rows
        )

        if still_waiting:
            if leader.creation > give_up_cutoff:
                continue
            frappe.db.set_value("Event", leader.name, "custom_confirmation_link_pending", 0, update_modified=False)
            continue

        subject, message = _compose_meet_link_followup_message(event_rows, leader.custom_client)
        if subject:
            _send_confirmation_email(leader.custom_confirmation_recipient, subject, message, leader.name)

        frappe.db.set_value("Event", leader.name, "custom_confirmation_link_pending", 0, update_modified=False)

    frappe.db.commit()


def _compose_online_session_reminder_message(event_row, client, coach_name):
    start_dt = get_datetime(event_row.get("starts_on"))
    meet_link = event_row.get("custom_google_meet_url") or event_row.get("google_meet_link") or ""
    contact_name = _get_client_display_name(client)
    who_with = f" with {coach_name}" if coach_name else ""

    subject = "Your session starts in 1 hour"
    message = (
        f"Hi {contact_name},\n\n"
        f"Just a reminder - your online session{who_with} starts in 1 hour, "
        f"at {start_dt.strftime('%H:%M')} on {start_dt.strftime('%A %d %B %Y')}.\n\n"
        f"Here is the Google Meet link for easy access: {meet_link}\n\n"
        "Please let us know if you have any questions or need to make any changes.\n\n"
        "The Resilient Office"
    )

    return subject, message


def send_online_session_reminders():
    """
    Scheduled sweep (hooks.py, every 5 minutes) - a reminder email roughly
    REMINDER_LEAD_MINUTES before an online session starts, confirmed
    requested live (no reminder feature of any kind existed anywhere in
    this codebase before this). Online sessions only - an in-person
    session has no link worth reminding anyone of - and only once a
    Google Meet link actually exists, same reasoning as the confirmation
    flow above: no point reminding someone of a link that isn't there
    yet. custom_reminder_sent keeps this to exactly one send per event
    regardless of how many 5-minute sweeps land inside the matching
    window (see REMINDER_WINDOW_MINUTES's own comment for why that
    window is wider than the cron interval).
    """
    if not _event_has_field("custom_reminder_sent"):
        return

    half_window = REMINDER_WINDOW_MINUTES / 2
    window_start = add_to_date(now_datetime(), minutes=REMINDER_LEAD_MINUTES - half_window)
    window_end = add_to_date(now_datetime(), minutes=REMINDER_LEAD_MINUTES + half_window)

    fields = ["name", "starts_on", "location", "custom_client", "custom_google_meet_url"]
    if _event_has_field("custom_coach"):
        fields.append("custom_coach")
    if _event_has_field("google_meet_link"):
        fields.append("google_meet_link")

    events = frappe.get_all(
        "Event",
        filters={
            "starts_on": ["between", [window_start, window_end]],
            "custom_reminder_sent": 0,
        },
        fields=fields,
    )

    for event in events:
        if not _is_online_location(event.get("location")):
            continue

        meet_link = event.get("custom_google_meet_url") or event.get("google_meet_link") or ""
        if not meet_link:
            continue

        client = event.get("custom_client")
        if not client:
            continue

        email_options = get_client_email_options(client_name=client)
        recipient = email_options[0]["value"] if email_options else ""
        if not recipient:
            continue

        coach_name = _coach_label_from_name(event.get("custom_coach")) if event.get("custom_coach") else ""
        subject, message = _compose_online_session_reminder_message(event, client, coach_name)
        _send_confirmation_email(recipient, subject, message, event.name)

        frappe.db.set_value("Event", event.name, "custom_reminder_sent", 1, update_modified=False)

    frappe.db.commit()
