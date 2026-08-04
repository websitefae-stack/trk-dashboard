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


def _get_linked_item_labels_by_document(document_names):
	"""
	Which item(s)/workshop(s) each of the given Practice Documents is
	linked to (Practice Document Item, managed on the document itself in
	the Frappe Desk) - used to show what a Workshop Resource document is
	actually connected to on the coach's own Documents page, rather than
	a generic "Resource" label.
	"""
	if not document_names or not frappe.db.exists("DocType", "Practice Document Item"):
		return {}

	links = frappe.get_all(
		"Practice Document Item",
		filters={"parenttype": PRACTICE_DOCUMENT_DOCTYPE, "parent": ["in", document_names]},
		fields=["parent", "item"],
		ignore_permissions=True,
	)

	if not links:
		return {}

	item_codes = list({link.get("item") for link in links if link.get("item")})
	item_labels = {
		row.get("name"): row.get("item_name") or row.get("name")
		for row in frappe.get_all(
			"Item", filters={"name": ["in", item_codes]}, fields=["name", "item_name"], ignore_permissions=True,
		)
	}

	labels_by_document = {}
	for link in links:
		labels_by_document.setdefault(link.get("parent"), []).append(
			item_labels.get(link.get("item"), link.get("item"))
		)

	return labels_by_document


def _get_visible_resource_documents(user=None):
	"""
	Published Practice Documents that reach a coach without ever getting a
	Coach Document Requirement row - either because their purpose includes
	Client Resource ("Create assignments when published" only fires a
	requirement for Internal Compliance/Both), or because they're a
	Workshop Resource, which stays Internal Compliance on purpose (it's
	gated purely by Item Access via Resource Availability/Practice
	Document Coach, not the Applies To section's own audience, so it's in
	the same "nothing else surfaces this" position a Client Resource
	document is).
	"""
	rows = frappe.get_all(
		PRACTICE_DOCUMENT_DOCTYPE,
		filters={"status": "Published"},
		or_filters=[
			["document_purpose", "in", ("Client Resource", "Both")],
			["document_type", "=", "Workshop Resource"],
		],
		fields=[
			"name", "document_title", "document_code", "version",
			"document_type", "mandatory", "resource_availability", "document_file",
		],
		order_by="modified desc",
		ignore_permissions=True,
	)

	linked_labels = _get_linked_item_labels_by_document([row.name for row in rows])

	for row in rows:
		row["linked_items"] = linked_labels.get(row.name, [])

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


def _is_resource_reachable(source):
	"""
	True for anything _get_visible_resource_documents() would have listed -
	a genuine Client Resource/Both document, or a Workshop Resource (which
	stays Internal Compliance on purpose, gated by Item Access instead).
	Shared by get_resource_document/get_resource_document_file so a
	document that shows up on the list can always actually be opened.
	"""
	if source.status != "Published":
		return False

	return source.document_purpose in ("Client Resource", "Both") or source.document_type == "Workshop Resource"


@frappe.whitelist()
def get_resource_document(practice_document):
	"""
	The "Open Document" view for a resource document (never has a Coach
	Document Requirement, so nothing to read/acknowledge/sign - only
	summary/text/file and, when eligible, Allocate to Client).
	"""
	ensure_logged_in()

	if not practice_document or not frappe.db.exists(PRACTICE_DOCUMENT_DOCTYPE, practice_document):
		frappe.throw("You do not have permission to access this document.", frappe.PermissionError)

	source = frappe.get_doc(PRACTICE_DOCUMENT_DOCTYPE, practice_document)

	if not _is_resource_reachable(source):
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
		"additional_files": _get_additional_files(source),
		"summary": source.summary,
		"document_text": source.document_text,
		# Workshop Resources are internal-only, gated by Item Access - never
		# shareable with a client, unlike a genuine Client Resource/Both
		# document, regardless of what item(s) it's linked to.
		"can_allocate_to_client": source.document_purpose in ("Client Resource", "Both"),
	}


def _get_additional_files(source):
	"""[{"file": url, "label": label-or-filename}] for a Practice Document's
	Additional Files table - read live off the Practice Document itself
	rather than any snapshot, so a file added/removed there reaches
	whoever's already been assigned or can see this document immediately."""
	rows = []

	for row in source.get("additional_files") or []:
		file_url = row.get("file")
		if not file_url:
			continue

		rows.append({
			"file": file_url,
			"label": row.get("label") or file_url.split("?")[0].split("/")[-1],
		})

	return rows


def _serve_private_file(file_url):
	if not file_url:
		frappe.throw("No file is attached to this document.")

	from frappe.utils.file_manager import get_file

	fname, fcontent = get_file(file_url)

	frappe.local.response.filename = fname
	frappe.local.response.filecontent = fcontent
	frappe.local.response.type = "download"


@frappe.whitelist()
def get_resource_document_file(practice_document, file_url=None):
	"""
	Same private-attachment proxy as get_my_document_file(), scoped by
	resource visibility instead of requirement ownership. file_url is
	optional - omitted, this serves the main Document File; given, it
	must match one of this document's own Additional Files rows (never
	trusted blind, so this can't be used to read an arbitrary private
	file elsewhere on the site).
	"""
	ensure_logged_in()

	if not practice_document or not frappe.db.exists(PRACTICE_DOCUMENT_DOCTYPE, practice_document):
		frappe.throw("You do not have permission to access this document.", frappe.PermissionError)

	source = frappe.get_doc(PRACTICE_DOCUMENT_DOCTYPE, practice_document)

	if not _is_resource_reachable(source):
		frappe.throw("You do not have permission to access this document.", frappe.PermissionError)

	if not _can_user_see_resource(source.as_dict()) and not _is_admin(frappe.session.user):
		frappe.throw("You do not have permission to access this document.", frappe.PermissionError)

	if not file_url:
		_serve_private_file(source.document_file)
		return

	valid_files = {row.get("file") for row in _get_additional_files(source)}

	if file_url not in valid_files:
		frappe.throw("You do not have permission to access this file.", frappe.PermissionError)

	_serve_private_file(file_url)


@frappe.whitelist()
def get_my_document_file(requirement_name, file_url=None):
	"""
	Coach Document Requirement.document_file is a copy of the Practice
	Document's own Attach field value - the underlying File record is
	still attached to the Practice Document, which coaches can't read
	directly, so a direct link to it would 403. This proxies the
	download after confirming the requesting user owns this requirement.
	file_url is optional - omitted, this serves the requirement's own
	document_file snapshot; given, it must match one of the linked
	Practice Document's current Additional Files rows (read live, same
	as get_my_document_requirement() - never trusted blind).
	"""
	ensure_logged_in()

	if not requirement_name or not frappe.db.exists(COACH_DOCUMENT_REQUIREMENT_DOCTYPE, requirement_name):
		frappe.throw("You do not have permission to access this document.", frappe.PermissionError)

	requirement = frappe.get_doc(COACH_DOCUMENT_REQUIREMENT_DOCTYPE, requirement_name)

	if requirement.user != frappe.session.user and not _is_admin(frappe.session.user):
		frappe.throw("You do not have permission to access this document.", frappe.PermissionError)

	if not file_url:
		_serve_private_file(requirement.document_file)
		return

	if not requirement.practice_document or not frappe.db.exists(PRACTICE_DOCUMENT_DOCTYPE, requirement.practice_document):
		frappe.throw("You do not have permission to access this file.", frappe.PermissionError)

	source = frappe.get_doc(PRACTICE_DOCUMENT_DOCTYPE, requirement.practice_document)
	valid_files = {row.get("file") for row in _get_additional_files(source)}

	if file_url not in valid_files:
		frappe.throw("You do not have permission to access this file.", frappe.PermissionError)

	_serve_private_file(file_url)


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
		source = frappe.get_doc(PRACTICE_DOCUMENT_DOCTYPE, requirement.practice_document)
	else:
		source = None

	data["summary"] = source.get("summary") if source else None
	data["document_text"] = source.get("document_text") if source else None
	data["can_allocate_to_client"] = ((source.get("document_purpose") if source else None) or "") in ("Client Resource", "Both")
	data["additional_files"] = _get_additional_files(source) if source else []

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

	# This app does its own access check above (_get_owned_requirement) -
	# coaches have no Frappe role permission on this doctype at all (they
	# never touch it outside these whitelisted endpoints), so without this
	# submit() throws a PermissionError before the Before Submit Server
	# Script that actually completes the requirement ever gets to run.
	requirement.flags.ignore_permissions = True
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


# Only these actually need someone to go and DO something - a "Read Only"
# document is just a file sitting in the library for people to open if/when
# they need it, so it doesn't belong in the notifications inbox at all.
REQUIRED_ACTION_NOTIFICATION_TYPE = {
	"Acknowledge": "Task",
	"Sign": "Approval Request",
}


def notify_requirement_assigned(doc, method=None):
	if not doc.user:
		return

	notification_type = REQUIRED_ACTION_NOTIFICATION_TYPE.get(doc.required_action)

	if not notification_type:
		return

	try:
		create_trk_notification(
			recipient_user=doc.user,
			notification_type=notification_type,
			message="A new document needs your {0}: {1}".format(
				"signature" if doc.required_action == "Sign" else "acknowledgement",
				doc.document_title or doc.practice_document,
			),
			priority="High" if doc.mandatory else "Normal",
			reference_doctype=COACH_DOCUMENT_REQUIREMENT_DOCTYPE,
			reference_name=doc.name,
		)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Document Assigned Notification Failed")


# Fields the user's own "Prepare coach document requirement" Server
# Script (Before Insert) copies from the Practice Document onto a Coach
# Document Requirement - a one-off snapshot taken when the requirement
# is first created, not a live reference. {practice_document_field:
# requirement_field}.
REQUIREMENT_SNAPSHOT_FIELDS = {
	"document_title": "document_title",
	"document_code": "document_code",
	"version": "document_version",
	"document_type": "document_type",
	"mandatory": "mandatory",
	"required_action": "required_action",
	"document_file": "document_file",
	"acknowledgement_statement": "acknowledgement_declaration",
	"signature_statement": "signature_declaration",
}


def sync_requirement_snapshot_fields(doc, method=None):
	"""
	Practice Document.on_update hook - because REQUIREMENT_SNAPSHOT_FIELDS
	is only ever copied once, at creation, editing the Practice Document
	afterward (e.g. changing Required Action from Sign to Acknowledge, or
	fixing a typo in the declaration text) never reached a requirement
	created before that edit - it kept showing whatever was true when it
	was first assigned, which is exactly why some policies were showing a
	signature block and others weren't for what should be the same
	setting. Only ever touches requirements not yet completed
	(docstatus != 1) - a completed one is a historical record of what was
	actually agreed to, and must never be silently rewritten after the
	fact.
	"""
	if not doc.name:
		return

	try:
		requirement_names = frappe.get_all(
			COACH_DOCUMENT_REQUIREMENT_DOCTYPE,
			filters={"practice_document": doc.name, "docstatus": ["!=", 1]},
			pluck="name",
		)

		if not requirement_names:
			return

		requirement_meta = frappe.get_meta(COACH_DOCUMENT_REQUIREMENT_DOCTYPE)
		updates = {}

		for practice_field, requirement_field in REQUIREMENT_SNAPSHOT_FIELDS.items():
			if doc.meta.has_field(practice_field) and requirement_meta.has_field(requirement_field):
				updates[requirement_field] = doc.get(practice_field)

		if not updates:
			return

		for requirement_name in requirement_names:
			frappe.db.set_value(
				COACH_DOCUMENT_REQUIREMENT_DOCTYPE, requirement_name, updates, update_modified=False,
			)
	except Exception:
		frappe.log_error(frappe.get_traceback(), f"Requirement Snapshot Resync Failed - {doc.name}")
