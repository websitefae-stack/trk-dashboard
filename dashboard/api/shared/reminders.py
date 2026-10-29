"""
Personal reminders for a dashboard user (currently only built into the
franchisor UI, but scoped by frappe.session.user throughout rather than
any particular role, so nothing stops another dashboard surface reusing
it later) - e.g. "speak to the office about price increases" every 1st
of November. A reminder fires into the same in-app notification system
(create_trk_notification) everything else in this app already uses, on
or after its own remind_date, then either rolls its date forward (a
recurring one) or deactivates itself (a one-off).
"""

import frappe
from frappe import _
from frappe.utils import getdate, nowdate, add_to_date

from dashboard.api.shared.permissions import ensure_logged_in
from dashboard.api.shared.notifications import create_trk_notification

DOCTYPE = "Dashboard Reminder"
RECURRENCE_OPTIONS = ("Weekly", "Monthly", "Yearly")


def _get_own_reminder(name):
	name = (name or "").strip()
	if not name or not frappe.db.exists(DOCTYPE, name):
		frappe.throw(_("Reminder not found."))

	doc = frappe.get_doc(DOCTYPE, name)
	if doc.user != frappe.session.user:
		frappe.throw(_("You do not have permission to access this reminder."), frappe.PermissionError)

	return doc


@frappe.whitelist()
def get_my_reminders():
	ensure_logged_in()

	return frappe.get_all(
		DOCTYPE,
		filters={"user": frappe.session.user},
		fields=["name", "title", "note", "remind_date", "recurrence", "active"],
		order_by="remind_date asc",
		ignore_permissions=True,
	)


@frappe.whitelist()
def create_reminder(title=None, note=None, remind_date=None, recurrence=None):
	ensure_logged_in()

	title = (title or "").strip()
	if not title:
		frappe.throw(_("Please enter a title for this reminder."))

	if not remind_date:
		frappe.throw(_("Please choose a date."))

	doc = frappe.get_doc({
		"doctype": DOCTYPE,
		"title": title,
		"note": (note or "").strip(),
		"user": frappe.session.user,
		"remind_date": getdate(remind_date),
		"recurrence": recurrence if recurrence in RECURRENCE_OPTIONS else "None",
		"active": 1,
	})
	doc.insert(ignore_permissions=True)

	return {"name": doc.name}


@frappe.whitelist()
def update_reminder(name=None, title=None, note=None, remind_date=None, recurrence=None, active=None):
	ensure_logged_in()

	doc = _get_own_reminder(name)

	if title is not None:
		title = title.strip()
		if not title:
			frappe.throw(_("Please enter a title for this reminder."))
		doc.title = title

	if note is not None:
		doc.note = note.strip()

	if remind_date is not None:
		doc.remind_date = getdate(remind_date)
		# A reminder that already fired today but is then moved - to today
		# or earlier - should be eligible to fire again on its new date,
		# not silently skipped by send_due_reminders()'s own-day guard.
		doc.last_fired_on = None

	if recurrence is not None:
		doc.recurrence = recurrence if recurrence in RECURRENCE_OPTIONS else "None"

	if active is not None:
		doc.active = 1 if int(active) else 0

	doc.save(ignore_permissions=True)

	return {"ok": 1}


@frappe.whitelist()
def delete_reminder(name=None):
	ensure_logged_in()

	doc = _get_own_reminder(name)
	frappe.delete_doc(DOCTYPE, doc.name, ignore_permissions=True)

	return {"ok": 1}


def _advance_remind_date(remind_date, recurrence):
	remind_date = getdate(remind_date)

	if recurrence == "Weekly":
		return add_to_date(remind_date, days=7)
	if recurrence == "Monthly":
		return add_to_date(remind_date, months=1)
	if recurrence == "Yearly":
		return add_to_date(remind_date, years=1)

	return remind_date


def _fire_reminder(row):
	message = row.get("title") or ""
	if row.get("note"):
		message += " - " + row["note"]

	create_trk_notification(
		recipient_user=row.get("user"),
		notification_type="Task",
		message=message,
		reference_doctype=DOCTYPE,
		reference_name=row.get("name"),
	)

	updates = {"last_fired_on": nowdate()}

	if row.get("recurrence") in RECURRENCE_OPTIONS:
		updates["remind_date"] = _advance_remind_date(row.get("remind_date"), row.get("recurrence"))
	else:
		updates["active"] = 0

	frappe.db.set_value(DOCTYPE, row.get("name"), updates, update_modified=False)


def send_due_reminders():
	"""
	Daily scheduled job (see hooks.py scheduler_events["daily"]). Picks up
	every active reminder whose remind_date has arrived (today or, if a
	scheduler run was missed, overdue), skips anything that's already
	fired today (last_fired_on), and otherwise notifies its owner and
	either rolls the date forward (recurring) or deactivates it (one-off)
	via _fire_reminder().
	"""
	today = nowdate()

	rows = frappe.get_all(
		DOCTYPE,
		filters={"active": 1, "remind_date": ["<=", today]},
		fields=["name", "title", "note", "user", "remind_date", "recurrence", "last_fired_on"],
	)

	for row in rows:
		if row.get("last_fired_on") and getdate(row["last_fired_on"]) >= getdate(today):
			continue

		try:
			_fire_reminder(row)
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"Dashboard Reminder Fire Failed - {row.get('name')}")
