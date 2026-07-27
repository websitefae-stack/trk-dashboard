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
from frappe.utils import now_datetime

from dashboard.api.shared.permissions import ensure_logged_in, get_allowed_client_names
from dashboard.api.shared.notifications import create_trk_notification

COACH_DOCUMENT_REQUIREMENT_DOCTYPE = "Coach Document Requirement"
PRACTICE_DOCUMENT_DOCTYPE = "Practice Document"
CLIENT_DOCUMENT_SHARE_DOCTYPE = "Client Document Share"


def _is_admin(user):
	if user == "Administrator":
		return True
	return "System Manager" in frappe.get_roles(user)


def _document_type_options():
	options = frappe.get_meta(PRACTICE_DOCUMENT_DOCTYPE).get_field("document_type").options or ""
	return [option.strip() for option in options.split("\n") if option.strip()]


def _can_user_see_resource(document, user=None):
	"""
	document is a dict with at least resource_availability + name.
	"All Coaches" means every logged-in dashboard user; "Selected Coaches"
	is gated by a Practice Document Coach row naming this user, matching
	Practice Document's own "Available to Coaches" field description.
	"""
	user = user or frappe.session.user

	if document.get("resource_availability") != "Selected Coaches":
		return True

	return bool(frappe.db.exists(
		"Practice Document Coach",
		{
			"parent": document.get("name"),
			"parenttype": PRACTICE_DOCUMENT_DOCTYPE,
			"user": user,
			"can_share": 1,
		},
	))


def _get_visible_resource_documents(user=None):
	"""
	Published Practice Documents whose purpose includes Client Resource -
	these never get a Coach Document Requirement (see "Create assignments
	when published": only Internal Compliance/Both create one), so this is
	the only way the Documents page can ever show them.
	"""
	rows = frappe.get_all(
		PRACTICE_DOCUMENT_DOCTYPE,
		filters={
			"status": "Published",
			"document_purpose": ["in", ("Client Resource", "Both")],
		},
		fields=[
			"name", "document_title", "document_code", "version",
			"document_type", "mandatory", "resource_availability", "document_file",
		],
		order_by="modified desc",
		ignore_permissions=True,
	)

	return [row for row in rows if _can_user_see_resource(row, user=user)]


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
		row["kind"] = "requirement"
		key = row.document_type if row.document_type in documents else "Other"
		documents[key].append(row)

	for row in _get_visible_resource_documents(user=user):
		row["kind"] = "resource"
		row["document_version"] = row.get("version")
		key = row.document_type if row.document_type in documents else "Other"
		documents[key].append(row)

	return {"types": types, "documents": documents}


@frappe.whitelist()
def get_resource_document(practice_document):
	"""
	The "Open Document" view for a pure Client Resource document (never
	has a Coach Document Requirement, so nothing to read/acknowledge/sign -
	only summary/text/file and, when eligible, Allocate to Client).
	"""
	ensure_logged_in()

	if not practice_document or not frappe.db.exists(PRACTICE_DOCUMENT_DOCTYPE, practice_document):
		frappe.throw("You do not have permission to access this document.", frappe.PermissionError)

	source = frappe.get_doc(PRACTICE_DOCUMENT_DOCTYPE, practice_document)

	if source.status != "Published" or source.document_purpose not in ("Client Resource", "Both"):
		frappe.throw("You do not have permission to access this document.", frappe.PermissionError)

	if not _can_user_see_resource(source.as_dict()) and not _is_admin(frappe.session.user):
		frappe.throw("You do not have permission to access this document.", frappe.PermissionError)

	return {
		"name": source.name,
		"document_title": source.document_title,
		"document_code": source.document_code,
		"document_version": source.version,
		"document_type": source.document_type,
		"mandatory": source.mandatory,
		"document_file": source.document_file,
		"summary": source.summary,
		"document_text": source.document_text,
		"can_allocate_to_client": True,
	}


@frappe.whitelist()
def get_resource_document_file(practice_document):
	"""Same private-attachment proxy as get_my_document_file(), scoped by resource visibility instead of requirement ownership."""
	ensure_logged_in()

	if not practice_document or not frappe.db.exists(PRACTICE_DOCUMENT_DOCTYPE, practice_document):
		frappe.throw("You do not have permission to access this document.", frappe.PermissionError)

	source = frappe.get_doc(PRACTICE_DOCUMENT_DOCTYPE, practice_document)

	if source.status != "Published" or source.document_purpose not in ("Client Resource", "Both"):
		frappe.throw("You do not have permission to access this document.", frappe.PermissionError)

	if not _can_user_see_resource(source.as_dict()) and not _is_admin(frappe.session.user):
		frappe.throw("You do not have permission to access this document.", frappe.PermissionError)

	if not source.document_file:
		frappe.throw("No file is attached to this document.")

	from frappe.utils.file_manager import get_file

	fname, fcontent = get_file(source.document_file)

	frappe.local.response.filename = fname
	frappe.local.response.filecontent = fcontent
	frappe.local.response.type = "download"


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


def _get_owned_requirement(requirement_name):
	ensure_logged_in()

	if not requirement_name or not frappe.db.exists(COACH_DOCUMENT_REQUIREMENT_DOCTYPE, requirement_name):
		frappe.throw("You do not have permission to access this document.", frappe.PermissionError)

	requirement = frappe.get_doc(COACH_DOCUMENT_REQUIREMENT_DOCTYPE, requirement_name)

	if requirement.user != frappe.session.user and not _is_admin(frappe.session.user):
		frappe.throw("You do not have permission to access this document.", frappe.PermissionError)

	return requirement


@frappe.whitelist()
def get_my_document_requirement(requirement_name):
	"""
	Everything the in-dashboard "Open Document" view needs: the
	requirement itself, plus the summary/document text/purpose that only
	live on the linked Practice Document (never duplicated onto the
	requirement's own snapshot fields).
	"""
	requirement = _get_owned_requirement(requirement_name)
	data = requirement.as_dict()

	if requirement.practice_document and frappe.db.exists(PRACTICE_DOCUMENT_DOCTYPE, requirement.practice_document):
		source = frappe.db.get_value(
			PRACTICE_DOCUMENT_DOCTYPE,
			requirement.practice_document,
			["summary", "document_text", "document_purpose", "shareable_with", "client_action_required"],
			as_dict=True,
		)
	else:
		source = {}

	data["summary"] = source.get("summary")
	data["document_text"] = source.get("document_text")
	data["can_allocate_to_client"] = (source.get("document_purpose") or "") in ("Client Resource", "Both")

	return data


@frappe.whitelist()
def complete_my_document_requirement(
	requirement_name,
	read_confirmed=None,
	acknowledgement_confirmed=None,
	typed_full_name=None,
	signature=None,
	signature_confirmed=None,
):
	"""
	Sets only the completion fields the coach filled in, then calls
	requirement.submit() - never frappe.db.set_value(..., "docstatus", 1) -
	so the user's own "Complete coach document requirement" Server Script
	(Before Submit) is what actually validates and finishes this, exactly
	as it does when submitted from the Desk form.
	"""
	requirement = _get_owned_requirement(requirement_name)

	if requirement.docstatus != 0:
		frappe.throw("This document has already been completed.")

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
		frappe.db.set_value(COACH_DOCUMENT_REQUIREMENT_DOCTYPE, requirement.name, updates)

	requirement.reload()
	requirement.submit()

	return {
		"ok": True,
		"status": requirement.status,
		"completed_on": requirement.completed_on,
		"completion_reference": requirement.completion_reference,
	}


def _truthy(value):
	return str(value).strip().lower() in ("1", "true", "yes", "on")


@frappe.whitelist()
def get_allocation_target_clients():
	ensure_logged_in()

	names = get_allowed_client_names()

	if not names:
		return []

	rows = frappe.get_all(
		"Client",
		filters={"name": ["in", names]},
		fields=["name", "full_name", "name1"],
		order_by="full_name asc",
		ignore_permissions=True,
	)

	for row in rows:
		row["display_name"] = row.get("full_name") or row.get("name1") or row.get("name")

	return rows


@frappe.whitelist()
def allocate_document_to_client(requirement_name=None, practice_document=None, client=None, recipient_type=None, message=None):
	"""
	Records that a coach/franchisor/session worker has decided to share
	this document with a client - creates a Client Document Share row
	(Prepared) for whoever handles delivery to pick up. Does not itself
	send anything. Works from either an owned Coach Document Requirement
	(Internal Compliance/Both documents someone was assigned) or directly
	from a Practice Document (pure Client Resource documents, which never
	get a requirement row at all).
	"""
	if requirement_name:
		requirement = _get_owned_requirement(requirement_name)
		practice_document_name = requirement.practice_document
		document_title = requirement.document_title
		document_code = requirement.document_code
		document_version = requirement.document_version
		client_action_required = requirement.required_action
		coach = requirement.coach
		session_worker = requirement.session_worker
	elif practice_document:
		source_data = get_resource_document(practice_document)
		practice_document_name = source_data["name"]
		document_title = source_data["document_title"]
		document_code = source_data["document_code"]
		document_version = source_data["document_version"]
		client_action_required = frappe.db.get_value(PRACTICE_DOCUMENT_DOCTYPE, practice_document_name, "client_action_required")
		coach = frappe.db.get_value("Coach", {"user": frappe.session.user}, "name")
		session_worker = frappe.db.get_value("Session Worker", {"user": frappe.session.user}, "name")
	else:
		frappe.throw("A document is required.")

	document_purpose = frappe.db.get_value(PRACTICE_DOCUMENT_DOCTYPE, practice_document_name, "document_purpose")

	if document_purpose not in ("Client Resource", "Both"):
		frappe.throw("This document is not available to share with clients.")

	if not client:
		frappe.throw("Choose a client.")

	if client not in (get_allowed_client_names() or []):
		frappe.throw("You do not have permission to access this client.", frappe.PermissionError)

	if not recipient_type:
		frappe.throw("Choose a recipient type.")

	share = frappe.new_doc(CLIENT_DOCUMENT_SHARE_DOCTYPE)
	share.practice_document = practice_document_name
	share.document_title = document_title
	share.document_code = document_code
	share.document_version = document_version
	share.client_action_required = client_action_required

	share.shared_by = frappe.session.user
	share.shared_on = now_datetime()
	share.coach = coach
	share.session_worker = session_worker

	share.client = client
	share.recipient_type = recipient_type
	share.delivery_method = "Secure Portal Link"
	share.coach_message = message or ""
	share.status = "Prepared"
	share.created_from_dashboard = 1

	share.insert(ignore_permissions=True)

	return {"ok": True, "name": share.name}


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
