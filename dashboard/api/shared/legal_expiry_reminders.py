"""
Daily reminders to coaches and session workers whose DBS (or DBS
Update Service), Insurance, or ICO Certificate is about to expire - at
30 days, 7 days and 1 day before the expiry that actually matters for
compliance.

Ashley's own words: people were forgetting, letting it lapse, getting
locked out of the dashboard (see permissions.enforce_legal_compliance)
and then having to "run around" afterwards to sort it out. This is
meant to catch it well before that point, by reusing the exact same
"which row is the one that counts" logic enforce_legal_compliance
already uses (permissions._latest_dated_row / the combined DBS + DBS
Update Service rule - see get_expired_legal_items's own docstring) so
a reminder's countdown always tracks the same date that would actually
lock them out, never a stale/superseded row.

Session Workers are included deliberately (Ashley confirmed) - they
have the exact same three fields and the exact same lockout risk, just
under slightly different fieldnames (see _DASHBOARD_CONFIG below).

Runs once a day (see hooks.py's "0 10 * * *" cron entry, the same slot
this app's other predictable-hour notification jobs use). A reminder
only fires on the exact day a threshold is crossed (days_until == 30,
7 or 1) rather than being deduped via a cache - simpler, and it means
a missed run (e.g. the site was down that day) just results in that
one threshold being skipped rather than a backlog of repeats; the
coach still gets whichever of the later thresholds comes next.
"""

import frappe

from dashboard.api.shared.item_access import _get_coach_login
from dashboard.api.shared.notifications import create_trk_notification
from dashboard.api.shared.permissions import _latest_dated_row
from dashboard.api.shared.practice_documents import _get_session_worker_login

THRESHOLD_DAYS = (30, 7, 1)

_DASHBOARD_CONFIG = {
    "coach": {
        "doctype": "Coach",
        "dbs_update_field": "dbs_update_services",
        "login_resolver": _get_coach_login,
    },
    "session_worker": {
        "doctype": "Session Worker",
        "dbs_update_field": "dbs_update_service",
        "login_resolver": _get_session_worker_login,
    },
}

_PLAIN_TABLES = [
    ("Insurance", "insurance", "insurance_number"),
    ("ICO Certificate", "indemnity", "indemnity_number"),
]


def _due_soon_items(doc, config, today):
    due = []

    dbs_best = _latest_dated_row(doc.get("dbs"), "dbs_number")
    update_best = _latest_dated_row(doc.get(config["dbs_update_field"]), "dbs_number")
    dbs_family_best = max(
        (row for row in (dbs_best, update_best) if row),
        key=lambda row: row["expiry"],
        default=None,
    )

    if dbs_family_best:
        days_until = (dbs_family_best["expiry"] - today).days
        if days_until in THRESHOLD_DAYS:
            due.append(("DBS", dbs_family_best["expiry_date"], days_until))

    for label, table_field, number_field in _PLAIN_TABLES:
        best = _latest_dated_row(doc.get(table_field), number_field)
        if not best:
            continue

        days_until = (best["expiry"] - today).days
        if days_until in THRESHOLD_DAYS:
            due.append((label, best["expiry_date"], days_until))

    return due


def _reminder_message(label, expiry_date, days_until):
    when = "tomorrow" if days_until == 1 else f"in {days_until} days"
    return (
        f"Your {label} is due to expire {when} (on {expiry_date}). Please renew it and upload the new "
        "document on your Profile page before it lapses - otherwise you'll be locked out of the dashboard "
        "until it's sorted."
    )


def send_legal_expiry_reminders():
    today = frappe.utils.getdate(frappe.utils.today())

    for dashboard_type, config in _DASHBOARD_CONFIG.items():
        doctype = config["doctype"]
        if not frappe.db.exists("DocType", doctype):
            continue

        for name in frappe.get_all(doctype, pluck="name"):
            try:
                doc = frappe.get_doc(doctype, name)
            except Exception:
                continue

            due_items = _due_soon_items(doc, config, today)
            if not due_items:
                continue

            recipient_user = config["login_resolver"](name)
            if not recipient_user:
                continue

            for label, expiry_date, days_until in due_items:
                try:
                    create_trk_notification(
                        recipient_user=recipient_user,
                        notification_type="Task",
                        message=_reminder_message(label, expiry_date, days_until),
                        priority="High" if days_until == 1 else "Normal",
                        reference_doctype=doctype,
                        reference_name=name,
                        coach=name if dashboard_type == "coach" else None,
                        session_worker=name if dashboard_type == "session_worker" else None,
                    )
                except Exception:
                    frappe.log_error(
                        frappe.get_traceback(), f"Legal Expiry Reminder Failed - {doctype} {name}"
                    )
