"""
Publishing a Practice Document is the single trigger for the whole
compliance assignment system: every active Coach (including franchisors,
who are Coach records too - see permissions.FRANCHISOR_USERS) and every
active Session Worker gets a Coach Document Requirement, snapshotting this
document's fields at the moment of publish so a later edit/republish of
the Practice Document can never silently change what someone already
agreed to.

This only ever creates NEW requirements (or supersedes an older open one
for the same document_code) - it never touches a requirement that's
already Completed or Superseded, and re-saving an already-published
document simply tops up anyone missing a requirement (e.g. a coach who
joined after the first publish) without re-notifying anyone who already
has one. See coach_document_requirement.py for the submission-side audit
script and compliance.py for the notification job this queues up.
"""

import frappe
from frappe.model.document import Document
from frappe.utils import today, add_days

FRANCHISOR_USERS = {
	"ashley@theresilientkid.co.uk",
	"office@theresilienthub.co.uk",
	"hq@theresilientkid.co.uk",
}

OPEN_STATUSES = ["Not Viewed", "Viewed", "In Progress", "Overdue"]


class PracticeDocument(Document):
	def validate(self):
		if self.status == "Published" and not self.published_date:
			self.published_date = today()

	def on_update(self):
		if self.status == "Published":
			create_requirements_for_published_document(self)


def _get_recipients():
	recipients = []

	for coach in frappe.get_all(
		"Coach",
		filters={"user": ["is", "set"]},
		fields=["name", "user", "coach_name"],
	):
		person_type = "Franchisor" if (coach.user or "").strip().lower() in FRANCHISOR_USERS else "Coach"
		recipients.append({
			"person_type": person_type,
			"coach": coach.name,
			"session_worker": None,
			"user": coach.user,
		})

	for session_worker in frappe.get_all(
		"Session Worker",
		filters={"user": ["is", "set"]},
		fields=["name", "user", "sw_name"],
	):
		recipients.append({
			"person_type": "Session Worker",
			"coach": None,
			"session_worker": session_worker.name,
			"user": session_worker.user,
		})

	return recipients


def create_requirements_for_published_document(practice_document):
	assigned_by = frappe.session.user if frappe.session.user != "Guest" else "Administrator"
	due_date = (
		add_days(practice_document.published_date or today(), practice_document.completion_days)
		if practice_document.completion_days
		else None
	)

	for recipient in _get_recipients():
		user = recipient["user"]
		if not user:
			continue

		already_assigned = frappe.db.exists(
			"Coach Document Requirement",
			{
				"practice_document": practice_document.name,
				"user": user,
				"document_version": practice_document.version,
			},
		)
		if already_assigned:
			continue

		prior_open_names = frappe.get_all(
			"Coach Document Requirement",
			filters={
				"document_code": practice_document.document_code,
				"user": user,
				"docstatus": 0,
				"status": ["in", OPEN_STATUSES],
			},
			pluck="name",
		)

		requirement = frappe.new_doc("Coach Document Requirement")
		requirement.person_type = recipient["person_type"]
		requirement.coach = recipient["coach"]
		requirement.session_worker = recipient["session_worker"]
		requirement.user = user
		requirement.assigned_by = assigned_by
		requirement.assigned_date = today()
		requirement.due_date = due_date
		requirement.practice_document = practice_document.name
		requirement.document_title = practice_document.document_title
		requirement.document_code = practice_document.document_code
		requirement.document_version = practice_document.version
		requirement.document_type = practice_document.document_type
		requirement.mandatory = practice_document.mandatory
		requirement.required_action = practice_document.required_action
		requirement.document_file = practice_document.document_file
		requirement.status = "Not Viewed"

		for row in practice_document.get("category") or []:
			requirement.append("category", {"category_name": row.category_name})

		requirement.insert(ignore_permissions=True)

		for prior_name in prior_open_names:
			frappe.db.set_value(
				"Coach Document Requirement",
				prior_name,
				{"status": "Superseded", "superseded_by": requirement.name},
			)

	frappe.db.commit()
