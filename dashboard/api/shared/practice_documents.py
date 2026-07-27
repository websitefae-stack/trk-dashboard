"""
Dashboard-facing reads for Practice Document / Coach Document Requirement,
and the "a document was allocated to you" notification. This deliberately
never touches assignment, validation or completion - all of that already
lives in the user's own Server Scripts / Client Script attached to these
DocTypes in Frappe Desk. This file only reads what those scripts already
produced, and notifies once a Coach Document Requirement has been
inserted.
"""

import frappe

from dashboard.api.shared.permissions import ensure_logged_in
from dashboard.api.shared.notifications import create_trk_notification

COACH_DOCUMENT_REQUIREMENT_DOCTYPE = "Coach Document Requirement"
PRACTICE_DOCUMENT_DOCTYPE = "Practice Document"


def _is_admin(user):
	if user == "Administrator":
		return True
	return "System Manager" in frappe.get_roles(user)


def _document_type_options():
	options = frappe.get_meta(PRACTICE_DOCUMENT_DOCTYPE).get_field("document_type").options or ""
	return [option.strip() for option in options.split("\n") if option.strip()]


@frappe.whitelist()
def get_my_documents_by_type():
	ensure_logged_in()
	user = frappe.session.user

	rows = frappe.get_all(
		COACH_DOCUMENT_REQUIREMENT_DOCTYPE,
		filters={"user": user},
		fields=[
			"name", "document_title", "document_code", "document_version",
			"document_type", "status", "mandatory", "due_date",
			"assigned_date", "completed_on",
		],
		order_by="assigned_date desc",
		ignore_permissions=True,
	)

	types = _document_type_options()
	documents = {document_type: [] for document_type in types}
	documents.setdefault("Other", [])

	for row in rows:
		key = row.document_type if row.document_type in documents else "Other"
		documents[key].append(row)

	return {"types": types, "documents": documents}


@frappe.whitelist()
def get_my_document_file(requirement_name):
	"""
	Coach Document Requirement.document_file is a copy of the Practice
	Document's own Attach field value - the underlying File record is
	still attached to the Practice Document, which coaches can't read
	directly, so a direct link to it would 403. This proxies the
	download after confirming the requesting user owns this requirement.
	"""
	ensure_logged_in()

	if not requirement_name or not frappe.db.exists(COACH_DOCUMENT_REQUIREMENT_DOCTYPE, requirement_name):
		frappe.throw("You do not have permission to access this document.", frappe.PermissionError)

	requirement = frappe.get_doc(COACH_DOCUMENT_REQUIREMENT_DOCTYPE, requirement_name)

	if requirement.user != frappe.session.user and not _is_admin(frappe.session.user):
		frappe.throw("You do not have permission to access this document.", frappe.PermissionError)

	if not requirement.document_file:
		frappe.throw("No file is attached to this document.")

	from frappe.utils.file_manager import get_file

	fname, fcontent = get_file(requirement.document_file)

	frappe.local.response.filename = fname
	frappe.local.response.filecontent = fcontent
	frappe.local.response.type = "download"


def notify_requirement_assigned(doc, method=None):
	if not doc.user:
		return

	try:
		create_trk_notification(
			recipient_user=doc.user,
			notification_type="Document Assigned",
			message="A new document has been assigned to you: {0}".format(doc.document_title or doc.practice_document),
			priority="High" if doc.mandatory else "Normal",
			reference_doctype=COACH_DOCUMENT_REQUIREMENT_DOCTYPE,
			reference_name=doc.name,
		)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Document Assigned Notification Failed")
