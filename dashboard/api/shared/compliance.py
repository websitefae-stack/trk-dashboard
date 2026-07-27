"""
"My Documents" - the dashboard-facing half of the Practice Document /
Coach Document Requirement compliance system. Assignment itself lives on
Practice Document (practice_document.py, triggered on publish) and the
Before Submit audit script lives on Coach Document Requirement
(coach_document_requirement.py) - this module only ever reads/updates
requirements that already exist and always completes them through
requirement.submit(), never by touching docstatus directly.

Every entry point here is scoped to frappe.session.user - a value from
the browser is never trusted as "which user's documents to show". See
_get_owned_requirement() for the one ownership check every other
function in this file goes through.
"""

import frappe
from frappe import _
from frappe.utils import today, now_datetime, formatdate, get_url

from dashboard.api.shared.permissions import ensure_logged_in
from dashboard.api.shared.notifications import create_trk_notification
from dashboard.api.shared.email_templates import plain_text_to_email_html

REQUIREMENT_DOCTYPE = "Coach Document Requirement"

OPEN_STATUSES = ["Not Viewed", "Viewed", "In Progress", "Overdue"]

STATUS_LABELS = {
	"Not Viewed": "New",
	"Viewed": "Viewed",
	"In Progress": "In Progress",
	"Overdue": "Overdue",
	"Completed": "Completed",
	"Superseded": "Superseded",
}


# -------------------------------------------------------------------
# Ownership / permissions
# -------------------------------------------------------------------

def _is_admin(user):
	if user == "Administrator":
		return True
	return "System Manager" in frappe.get_roles(user)


def _can_access_requirement(requirement, user=None):
	user = user or frappe.session.user
	if _is_admin(user):
		return True
	return requirement.get("user") == user


def _get_owned_requirement(requirement_name):
	ensure_logged_in()

	if not requirement_name or not frappe.db.exists(REQUIREMENT_DOCTYPE, requirement_name):
		frappe.throw(_("You do not have permission to access this document."), frappe.PermissionError)

	requirement = frappe.get_doc(REQUIREMENT_DOCTYPE, requirement_name)

	if not _can_access_requirement(requirement):
		frappe.throw(_("You do not have permission to access this document."), frappe.PermissionError)

	return requirement


def get_permission_query_conditions(user=None):
	if not user:
		user = frappe.session.user

	if _is_admin(user):
		return ""

	return "`tabCoach Document Requirement`.`user` = {0}".format(frappe.db.escape(user))


def has_permission(doc, ptype=None, user=None):
	# Coaches/session workers/franchisors only ever reach this doctype
	# through complete_document_requirement()'s requirement.submit() call
	# (everything else here goes through frappe.db.set_value, which never
	# checks permissions) - so beyond an owner's own read/submit, there is
	# nothing for this hook to legitimately grant. Explicitly denying
	# write/create/delete/cancel keeps that true regardless of whether a
	# given Frappe version lets this hook widen the base role grant, not
	# just narrow it.
	user = user or frappe.session.user

	if _is_admin(user):
		return True

	if not _can_access_requirement(doc, user=user):
		return False

	return ptype in ("read", "submit")


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def _truthy(value):
	return str(value).strip().lower() in ("1", "true", "yes", "on")


def _get_categories_for_requirements(names):
	if not names:
		return {}

	rows = frappe.get_all(
		"Compliance Category",
		filters={"parent": ["in", names], "parenttype": REQUIREMENT_DOCTYPE},
		fields=["parent", "category_name"],
		order_by="idx asc",
		ignore_permissions=True,
	)

	grouped = {}
	for row in rows:
		grouped.setdefault(row.parent, []).append(row.category_name)

	return grouped


def _outstanding_sort_key(row):
	is_overdue = 0 if row.get("status") == "Overdue" else 1
	due = row.get("due_date")
	due_sort = due if due else "9999-99-99"
	return (is_overdue, str(due_sort))


# -------------------------------------------------------------------
# API - dashboard card
# -------------------------------------------------------------------

@frappe.whitelist()
def get_my_document_summary():
	ensure_logged_in()
	user = frappe.session.user

	open_rows = frappe.get_all(
		REQUIREMENT_DOCTYPE,
		filters={"user": user, "docstatus": 0, "status": ["in", OPEN_STATUSES]},
		fields=["status", "due_date"],
		ignore_permissions=True,
	)

	overdue_count = len([row for row in open_rows if row.status == "Overdue"])
	completed_count = frappe.db.count(REQUIREMENT_DOCTYPE, {"user": user, "docstatus": 1, "status": "Completed"})
	total_count = frappe.db.count(REQUIREMENT_DOCTYPE, {"user": user, "status": ["!=", "Superseded"]})

	dated = [row.due_date for row in open_rows if row.due_date]
	next_due_date = min(dated) if dated else None

	return {
		"outstanding": len(open_rows),
		"overdue": overdue_count,
		"completed": completed_count,
		"total": total_count,
		"next_due_date": str(next_due_date) if next_due_date else None,
	}


# -------------------------------------------------------------------
# API - document list
# -------------------------------------------------------------------

@frappe.whitelist()
def get_my_documents(status_group=None):
	ensure_logged_in()
	user = frappe.session.user
	status_group = (status_group or "outstanding").strip().lower()

	fields = [
		"name", "document_title", "document_code", "document_version", "document_type",
		"required_action", "assigned_date", "due_date", "status", "mandatory",
		"completed_on", "docstatus",
	]

	if status_group == "completed":
		filters = {"user": user, "docstatus": 1, "status": "Completed"}
	elif status_group == "all":
		filters = {"user": user}
	else:
		status_group = "outstanding"
		filters = {"user": user, "docstatus": 0, "status": ["in", OPEN_STATUSES]}

	rows = frappe.get_all(REQUIREMENT_DOCTYPE, filters=filters, fields=fields, ignore_permissions=True)

	categories_by_name = _get_categories_for_requirements([row.name for row in rows])

	for row in rows:
		row["categories"] = categories_by_name.get(row.name, [])
		row["status_label"] = STATUS_LABELS.get(row.status, row.status)

	if status_group == "completed":
		rows.sort(key=lambda row: str(row.get("completed_on") or ""), reverse=True)
	elif status_group == "all":
		rows.sort(key=lambda row: str(row.get("assigned_date") or ""), reverse=True)
	else:
		rows.sort(key=_outstanding_sort_key)

	return rows


# -------------------------------------------------------------------
# API - single document
# -------------------------------------------------------------------

@frappe.whitelist()
def get_my_document_requirement(requirement_name):
	requirement = _get_owned_requirement(requirement_name)

	data = requirement.as_dict()
	data["categories"] = [row.category_name for row in requirement.get("category") or []]
	data["status_label"] = STATUS_LABELS.get(requirement.status, requirement.status)

	practice_document = None
	if requirement.practice_document and frappe.db.exists("Practice Document", requirement.practice_document):
		practice_document = frappe.db.get_value(
			"Practice Document",
			requirement.practice_document,
			["summary", "document_text"],
			as_dict=True,
		)

	data["practice_document_summary"] = (practice_document or {}).get("summary")
	data["practice_document_text"] = (practice_document or {}).get("document_text")

	return data


@frappe.whitelist()
def mark_document_viewed(requirement_name):
	requirement = _get_owned_requirement(requirement_name)

	now = now_datetime()
	updates = {
		"last_viewed_on": now,
		"view_count": (requirement.view_count or 0) + 1,
	}

	if not requirement.first_viewed_on:
		updates["first_viewed_on"] = now

	if requirement.docstatus == 0 and requirement.status not in ("Completed", "Overdue", "Superseded"):
		updates["status"] = "Viewed"

	frappe.db.set_value(REQUIREMENT_DOCTYPE, requirement.name, updates)
	frappe.db.commit()

	return {"ok": True}


@frappe.whitelist()
def complete_document_requirement(
	requirement_name,
	read_confirmed=None,
	acknowledgement_confirmed=None,
	typed_full_name=None,
	signature=None,
	signature_confirmed=None,
):
	requirement = _get_owned_requirement(requirement_name)

	if requirement.docstatus != 0:
		frappe.throw(_("This document has already been completed."))

	if requirement.status == "Superseded":
		frappe.throw(_("This document has been superseded and can no longer be completed."))

	updates = {}

	if requirement.required_action == "Read Only":
		updates["read_confirmed"] = 1 if _truthy(read_confirmed) else 0
	elif requirement.required_action == "Acknowledge":
		updates["acknowledgement_confirmed"] = 1 if _truthy(acknowledgement_confirmed) else 0
	elif requirement.required_action == "Sign":
		updates["typed_full_name"] = (typed_full_name or "").strip()
		updates["signature"] = signature or ""
		updates["signature_confirmed"] = 1 if _truthy(signature_confirmed) else 0

	if updates:
		frappe.db.set_value(REQUIREMENT_DOCTYPE, requirement.name, updates)
		frappe.db.commit()

	requirement.reload()
	requirement.submit()

	return {
		"ok": True,
		"status": requirement.status,
		"completed_on": requirement.completed_on,
		"completed_by": requirement.completed_by,
		"completion_reference": requirement.completion_reference,
	}


# -------------------------------------------------------------------
# Assignment notification (Coach Document Requirement.after_insert)
# -------------------------------------------------------------------

def on_requirement_created(doc, method=None):
	if doc.get("assignment_notification_sent"):
		return

	frappe.enqueue(
		"dashboard.api.shared.compliance.send_assignment_notification",
		queue="short",
		requirement_name=doc.name,
	)


def send_assignment_notification(requirement_name):
	if not frappe.db.exists(REQUIREMENT_DOCTYPE, requirement_name):
		return

	requirement = frappe.get_doc(REQUIREMENT_DOCTYPE, requirement_name)

	if requirement.get("assignment_notification_sent"):
		return

	due_date_display = formatdate(requirement.due_date) if requirement.due_date else "Not set"
	link = f"/coach-document/{requirement.name}"

	message = (
		"A new practice document has been assigned to you.\n\n"
		f"Document: {requirement.document_title}\n"
		f"Version: {requirement.document_version}\n"
		f"Action required: {requirement.required_action}\n"
		f"Due date: {due_date_display}\n\n"
		"Please log in to the dashboard to review and complete it."
	)

	try:
		create_trk_notification(
			recipient_user=requirement.user,
			notification_type="New Compliance Document",
			message=f"New document assigned: {requirement.document_title}\n\n{message}",
			priority="High" if requirement.mandatory else "Normal",
			reference_doctype=REQUIREMENT_DOCTYPE,
			reference_name=requirement.name,
		)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Compliance Assignment Notification - In-App Failed")

	try:
		frappe.sendmail(
			recipients=[requirement.user],
			subject=f"New document assigned: {requirement.document_title}",
			message=plain_text_to_email_html(f"{message}\n\nOpen it here: {get_url(link)}"),
			now=True,
			reference_doctype=REQUIREMENT_DOCTYPE,
			reference_name=requirement.name,
		)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Compliance Assignment Notification - Email Failed")

	try:
		if frappe.db.exists("DocType", "Notification Log"):
			notification = frappe.new_doc("Notification Log")
			notification.subject = f"New document assigned: {requirement.document_title}"
			notification.email_content = message
			notification.for_user = requirement.user
			notification.type = "Alert"
			notification.document_type = REQUIREMENT_DOCTYPE
			notification.document_name = requirement.name
			notification.from_user = frappe.session.user if frappe.session.user != "Guest" else "Administrator"
			notification.insert(ignore_permissions=True)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Compliance Assignment Notification - Notification Log Failed")

	frappe.db.set_value(
		REQUIREMENT_DOCTYPE,
		requirement.name,
		{"assignment_notification_sent": 1, "assignment_notification_sent_on": now_datetime()},
	)
	frappe.db.commit()


# -------------------------------------------------------------------
# Scheduled - overdue sweep
# -------------------------------------------------------------------

def mark_overdue_requirements():
	names = frappe.get_all(
		REQUIREMENT_DOCTYPE,
		filters={
			"docstatus": 0,
			"status": ["in", ["Not Viewed", "Viewed", "In Progress"]],
			"due_date": ["<", today()],
		},
		pluck="name",
	)

	for name in names:
		frappe.db.set_value(REQUIREMENT_DOCTYPE, name, "status", "Overdue")

	if names:
		frappe.db.commit()
