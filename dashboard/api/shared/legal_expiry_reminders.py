"""
Daily reminders to coaches and session workers about their DBS (or DBS
Update Service), Insurance, and ICO Certificate - at 30 days, 7 days
and 1 day before whichever date actually matters for compliance:

- A document that's on file but expiring soon - counts down to its own
  expiry_date, same as before.
- A document that's not on file at all - counts down to the end of its
  30-day grace period instead (see permissions.MISSING_DOCUMENT_GRACE_
  DAYS/get_expired_legal_items), starting from the day this job first
  notices it's missing and stamps dbs_missing_since/insurance_missing_
  since/ico_missing_since (see patches/add_legal_missing_since_fields.py)
  - a brand new "this document hasn't been provided" notification fires
  that same day, functioning as the "30 days" reminder for that case.

Both paths reuse the exact same "which row is the one that counts"
resolution permissions.get_expired_legal_items itself uses
(permissions._latest_dated_row / the combined DBS + DBS Update Service
rule), so a reminder's countdown always tracks the same date that would
actually lock the person out - never a stale/superseded row, and never
a different 30-day number than the one enforce_legal_compliance
actually enforces (both read permissions.MISSING_DOCUMENT_GRACE_DAYS).

Session Workers are included deliberately (Ashley confirmed) - they
have the exact same three fields and the exact same lockout risk, just
under slightly different DBS-Update-Service fieldnames (dbs_missing_
since/insurance_missing_since/ico_missing_since are the same name on
both doctypes - see _DASHBOARD_CONFIG below).

Runs once a day (see hooks.py's "0 10 * * *" cron entry, the same slot
this app's other predictable-hour notification jobs use), plus once
immediately on deploy (patches/run_legal_expiry_check_now.py) so a
backlog of already-missing/already-close-to-expiry documents is caught
straight away rather than waiting for the next 10am run. A reminder
only fires on the exact day a threshold is crossed rather than being
deduped via a cache - simpler, and it means a missed run (e.g. the site
was down) just results in that one threshold being skipped rather than
a backlog of repeats; the person still gets whichever of the later
thresholds comes next.

Office (OFFICE_USER) gets a copy of every one of these reminders too,
so Ashley can follow up and actually check the right document got
uploaded - not just hear about it once someone's already locked out
(permissions.notify_franchisors_of_expired_legal already covers that
later point, unchanged).
"""

import frappe

from dashboard.api.shared.item_access import _get_coach_login
from dashboard.api.shared.notifications import create_trk_notification, OFFICE_USER
from dashboard.api.shared.permissions import MISSING_DOCUMENT_GRACE_DAYS, _latest_dated_row
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

# (label, child table fieldname, number fieldname, missing-since fieldname)
# - same fieldname set covers both DBS-family (handled separately below,
# since it spans two tables) and the two plain tables.
_PLAIN_TABLES = [
    ("Insurance", "insurance", "insurance_number", "insurance_missing_since"),
    ("ICO Certificate", "indemnity", "indemnity_number", "ico_missing_since"),
]


def _sync_missing_since(doctype, name, doc, missing_since_field, is_missing, today):
    """
    Keeps dbs_missing_since/insurance_missing_since/ico_missing_since in
    step with reality: stamped with today's date the first time a
    requirement has nothing on file, cleared again as soon as it does.
    Returns the (possibly just-set) missing_since date, or None if the
    requirement isn't missing.
    """
    current = doc.get(missing_since_field)

    if not is_missing:
        if current:
            frappe.db.set_value(doctype, name, missing_since_field, None, update_modified=False)
        return None

    if current:
        return frappe.utils.getdate(current)

    frappe.db.set_value(doctype, name, missing_since_field, today, update_modified=False)
    return today


def _due_soon_items(doctype, name, doc, config, today):
    due = []

    dbs_best = _latest_dated_row(doc.get("dbs"), "dbs_number")
    update_best = _latest_dated_row(doc.get(config["dbs_update_field"]), "dbs_number")
    dbs_family_best = max(
        (row for row in (dbs_best, update_best) if row),
        key=lambda row: row["expiry"],
        default=None,
    )

    if dbs_family_best:
        _sync_missing_since(doctype, name, doc, "dbs_missing_since", False, today)
        days_until = (dbs_family_best["expiry"] - today).days
        if days_until in THRESHOLD_DAYS:
            due.append(("DBS", False, dbs_family_best["expiry_date"], days_until))
    else:
        missing_since = _sync_missing_since(doctype, name, doc, "dbs_missing_since", True, today)
        days_until = MISSING_DOCUMENT_GRACE_DAYS - (today - missing_since).days
        if days_until in THRESHOLD_DAYS:
            due.append(("DBS", True, None, days_until))

    for label, table_field, number_field, missing_since_field in _PLAIN_TABLES:
        best = _latest_dated_row(doc.get(table_field), number_field)

        if best:
            _sync_missing_since(doctype, name, doc, missing_since_field, False, today)
            days_until = (best["expiry"] - today).days
            if days_until in THRESHOLD_DAYS:
                due.append((label, False, best["expiry_date"], days_until))
        else:
            missing_since = _sync_missing_since(doctype, name, doc, missing_since_field, True, today)
            days_until = MISSING_DOCUMENT_GRACE_DAYS - (today - missing_since).days
            if days_until in THRESHOLD_DAYS:
                due.append((label, True, None, days_until))

    return due


def _reminder_message(label, is_missing, expiry_date, days_until):
    if is_missing:
        time_left = "until tomorrow" if days_until == 1 else f"{days_until} days"
        return (
            f"Your {label} is not on file. You have {time_left} to upload it on your Profile page "
            "before you're locked out of the dashboard until it's sorted."
        )

    when = "tomorrow" if days_until == 1 else f"in {days_until} days"
    return (
        f"Your {label} is due to expire {when} (on {expiry_date}). Please renew it and upload the new "
        "document on your Profile page before it lapses - otherwise you'll be locked out of the dashboard "
        "until it's sorted."
    )


def _office_reminder_message(person_name, label, is_missing, expiry_date, days_until):
    # A heads-up for office to follow up and check the right document
    # actually gets uploaded - not phrased as "your X", since this isn't
    # the coach/session worker's own document.
    if is_missing:
        time_left = "until tomorrow" if days_until == 1 else f"{days_until} days"
        return (
            f"{person_name}'s {label} is not on file - they've been reminded, with {time_left} left "
            "before they're locked out. Worth checking they actually sort it."
        )

    when = "tomorrow" if days_until == 1 else f"in {days_until} days"
    return (
        f"{person_name}'s {label} expires {when} (on {expiry_date}) - they've been reminded. "
        "Worth checking they renew it and upload the correct document."
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

            try:
                due_items = _due_soon_items(doctype, name, doc, config, today)
            except Exception:
                frappe.log_error(frappe.get_traceback(), f"Legal Expiry Check Failed - {doctype} {name}")
                continue

            if not due_items:
                continue

            recipient_user = config["login_resolver"](name)
            person_name = doc.get("coach_name") or doc.get("sw_name") or name

            for label, is_missing, expiry_date, days_until in due_items:
                if recipient_user:
                    try:
                        create_trk_notification(
                            recipient_user=recipient_user,
                            notification_type="Task",
                            message=_reminder_message(label, is_missing, expiry_date, days_until),
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

                # Office gets a copy of every reminder too, so Ashley can
                # follow up and confirm the right document actually gets
                # uploaded - not just hear about it once someone's
                # already locked out (see permissions.notify_franchisors_
                # of_expired_legal, which only fires at that later point).
                try:
                    create_trk_notification(
                        recipient_user=OFFICE_USER,
                        notification_type="Task",
                        message=_office_reminder_message(person_name, label, is_missing, expiry_date, days_until),
                        priority="High" if days_until == 1 else "Normal",
                        reference_doctype=doctype,
                        reference_name=name,
                        coach=name if dashboard_type == "coach" else None,
                        session_worker=name if dashboard_type == "session_worker" else None,
                    )
                except Exception:
                    frappe.log_error(
                        frappe.get_traceback(), f"Legal Expiry Office Reminder Failed - {doctype} {name}"
                    )

        frappe.db.commit()
