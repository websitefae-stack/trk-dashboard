"""
Drop-in replacement for frappe.sendmail() used across this app (and, via
cross-app import, resilient_domains/client_portal - same pattern already
used for dashboard.api.shared.appointment_types.is_publicly_bookable) -
exists because the office inbox (office@theresilienthub.co.uk) runs on
Titan's free plan, capped at 50 outgoing emails per rolling hour. Every
transactional email in this system (bookings, invoices, course access,
brochure/nurture sequences, school outreach) already goes through here,
so this is the one place that cap is ever actually enforced.

send_email() never drops or blocks a transactional send - it always
queues it (see why below) and just logs a warning if the hourly count
is already high, as an early signal that real volume is approaching the
cap (worth upgrading Titan's plan at that point, not fighting it with
ever-tighter throttling). send_bulk_batch() is for a future bulk sender
(e.g. the weekly newsletter, not built yet) - unlike send_email(), it
actually holds back recipients once the hour's budget is spent and hands
the remainder back to its caller to persist/retry later, since a
newsletter run is the one realistic way this site could blow past 50/hour
in a single go.

Always queues (now=False) rather than ever sending synchronously inside
a web request - a `now=True` send blocks that request on a live SMTP
round-trip to Titan, and bypasses Frappe's own Email Queue entirely,
which is also where the hourly count below is read from. Any `now=True`
passed in by a caller is silently dropped rather than honoured.
"""

import frappe
from frappe.utils import add_to_date, now_datetime

# Titan's free-plan cap is 50/hour - keep 5 of headroom rather than
# cutting it exactly, since the count below is a close-enough proxy
# (Email Queue rows created in the last hour) rather than Titan's own
# authoritative counter.
HOURLY_SEND_BUDGET = 45

# A bulk run (send_bulk_batch) never eats more than this much of the
# hour's budget, so a weekly newsletter mid-send can never lock out a
# real booking confirmation or order receipt landing in the same hour.
BULK_RESERVE_FOR_TRANSACTIONAL = 10


def _sent_in_last_hour():
    one_hour_ago = add_to_date(now_datetime(), hours=-1)
    return frappe.db.count("Email Queue", {"creation": [">=", one_hour_ago]})


def send_email(**kwargs):
    """Same keyword arguments as frappe.sendmail() - recipients, subject,
    message, reference_doctype, reference_name, cc, reply_to, etc."""
    kwargs["now"] = False

    sent_recently = _sent_in_last_hour()
    if sent_recently >= HOURLY_SEND_BUDGET:
        frappe.log_error(
            f"{sent_recently} emails already queued in the last hour - at or over the "
            f"{HOURLY_SEND_BUDGET}/hour safety budget (Titan's free plan caps outgoing mail "
            "at 50/hour). Sending this one anyway since a transactional email is never "
            "dropped, but this is worth a look - consider upgrading the Titan plan if this "
            "keeps happening.",
            "Email Throttle - Hourly Budget Exceeded",
        )

    frappe.sendmail(**kwargs)


def send_bulk_batch(recipients, build_subject, build_message, **kwargs):
    """
    For a future bulk/newsletter sender. Sends as many of `recipients` as
    the hour's remaining budget allows (after BULK_RESERVE_FOR_
    TRANSACTIONAL is set aside) and returns the rest unsent, so the
    caller can persist them and pick up again on a later scheduler tick
    (e.g. the next hour) rather than this blowing straight through the
    cap in one go. build_subject(recipient)/build_message(recipient) are
    called per recipient so each send can be personalised; kwargs are
    passed through to frappe.sendmail() for every send (e.g.
    reference_doctype, reference_name) with `now` always forced off.

    Returns {"sent_count": int, "pending_recipients": [...]}.
    """
    kwargs["now"] = False

    sent_recently = _sent_in_last_hour()
    remaining_budget = max(0, (HOURLY_SEND_BUDGET - BULK_RESERVE_FOR_TRANSACTIONAL) - sent_recently)

    to_send_now = list(recipients)[:remaining_budget]
    still_pending = list(recipients)[remaining_budget:]

    for recipient in to_send_now:
        frappe.sendmail(
            recipients=[recipient],
            subject=build_subject(recipient),
            message=build_message(recipient),
            **kwargs,
        )

    return {"sent_count": len(to_send_now), "pending_recipients": still_pending}
