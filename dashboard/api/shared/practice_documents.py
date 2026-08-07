"""
Dashboard-facing reads for Practice Document / Coach Document Requirement,
and the "a document was allocated to you" notification. Mostly this
deliberately never touches assignment, validation or completion - all of
that already lives in the user's own Server Scripts / Client Script
attached to these DocTypes in Frappe Desk, and this file only reads what
those scripts already produced. The one exception is brand-based
allocation (sync_practice_document_brand_requirements /
sync_coach_brand_document_requirements /
sync_session_worker_brand_document_requirements below) - a new
assignment route the Desk scripts have no concept of, so it's created
here instead, by inserting a bare Coach Document Requirement and letting
the existing "Prepare coach document requirement" Server Script (Before
Insert) fill it in exactly as it would for one created by hand. This is
now the ONLY assignment route this doctype has - the old Applies To
section (all_coaches/selected_assignments/etc) has been removed in
favour of brand-based access, so whatever Desk-side automation used to
create requirements off those fields needs removing too, since those
fields no longer exist to read.
"""

import frappe
from frappe.utils import now_datetime

from dashboard.api.shared.permissions import ensure_logged_in, get_allowed_client_names
from dashboard.api.shared.notifications import create_trk_notification
from dashboard.api.shared.item_access import _get_coach_login, _get_linked_item_codes, _get_coach_names_with_access_to_items
from dashboard.api.shared.coach_view_mode import get_coach_view_mode

COACH_DOCUMENT_REQUIREMENT_DOCTYPE = "Coach Document Requirement"
PRACTICE_DOCUMENT_DOCTYPE = "Practice Document"
PRACTICE_DOCUMENT_COACH_DOCTYPE = "Practice Document Coach"
CLIENT_DOCUMENT_SHARE_DOCTYPE = "Client Document Share"

# fieldname on Practice Document -> the matching Coach/Session Worker Brand
# Access.brand_access value (Desk-only doctypes, child tables on
# Coach.coach_brand_access / Session Worker.session_worker_brand_access -
# see resilient_domains' README "Coach Brand Access Fields" for Coach's
# options; Session Worker Brand Access is assumed to mirror that shape and
# is only ever queried behind a frappe.db.exists() guard, so this is a
# no-op rather than an error if that doctype turns out to be named or
# shaped differently on this site).
PRACTICE_DOCUMENT_BRAND_FIELDS = {
	"brand_access_kid": "Kid",
	"brand_access_teen": "Teen",
	"brand_access_people": "People",
	"brand_access_school": "School",
	"brand_access_franchise": "Franchise",
}

# Login fields tried in order to resolve a Session Worker's own sign-in
# identity - mirrors item_access.py's COACH_LOGIN_FIELDS convention.
SESSION_WORKER_LOGIN_FIELDS = ["user", "user_id", "email"]


def _get_session_worker_login(session_worker_name):
	meta = frappe.get_meta("Session Worker")

	for fieldname in SESSION_WORKER_LOGIN_FIELDS:
		if meta.has_field(fieldname):
			value = frappe.db.get_value("Session Worker", session_worker_name, fieldname)
			if value:
				return value

	return ""


def _is_admin(user):
	if user == "Administrator":
		return True
	return "System Manager" in frappe.get_roles(user)


def _resolve_effective_user(view_as=None, viewer=None):
	"""
	Read-only "View as Coach" support, mirroring calendar.py's
	_get_context_for_calendar_request - when the franchisor is viewing a
	specific coach (view_as/viewer, carried on the coach_db document pages
	while in view mode), every document read below must be scoped to that
	coach's own identity (Coach Document Requirement.user, Practice
	Document Coach membership) instead of the actual logged-in franchisor.
	Returns (effective_user, is_view_mode) - callers must also skip the
	_is_admin bypass while is_view_mode is true, so a franchisor viewing as
	a coach only ever sees exactly what that coach sees, nothing else.
	"""
	view_as = (view_as or "").strip()

	if not view_as:
		return frappe.session.user, False

	view_mode = get_coach_view_mode(scope=viewer, coach_name=view_as)

	if not view_mode.get("is_view_mode"):
		frappe.throw("You do not have permission to view this coach.", frappe.PermissionError)

	coach_user = _get_coach_login(view_mode.get("view_coach_name"))

	if not coach_user:
		frappe.throw("This coach does not have a dashboard login.")

	return coach_user, True


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
def get_my_documents_by_type(view_as=None, viewer=None):
	ensure_logged_in()
	user, _is_view_mode = _resolve_effective_user(view_as, viewer)

	rows = frappe.get_all(
		COACH_DOCUMENT_REQUIREMENT_DOCTYPE,
		filters={"user": user},
		fields=[
			"name", "document_title", "document_code", "document_version",
			"document_type", "status", "mandatory", "due_date",
			"assigned_date", "completed_on", "document_file",
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
def get_resource_document(practice_document, view_as=None, viewer=None):
	"""
	The "Open Document" view for a resource document (never has a Coach
	Document Requirement, so nothing to read/acknowledge/sign - only
	summary/text/file and, when eligible, Allocate to Client).
	"""
	ensure_logged_in()
	user, is_view_mode = _resolve_effective_user(view_as, viewer)

	if not practice_document or not frappe.db.exists(PRACTICE_DOCUMENT_DOCTYPE, practice_document):
		frappe.throw("You do not have permission to access this document.", frappe.PermissionError)

	source = frappe.get_doc(PRACTICE_DOCUMENT_DOCTYPE, practice_document)

	if not _is_resource_reachable(source):
		frappe.throw("You do not have permission to access this document.", frappe.PermissionError)

	if not _can_user_see_resource(source.as_dict(), user=user):
		if is_view_mode or not _is_admin(user):
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
def get_resource_document_file(practice_document, file_url=None, view_as=None, viewer=None):
	"""
	Same private-attachment proxy as get_my_document_file(), scoped by
	resource visibility instead of requirement ownership. file_url is
	optional - omitted, this serves the main Document File; given, it
	must match one of this document's own Additional Files rows (never
	trusted blind, so this can't be used to read an arbitrary private
	file elsewhere on the site).
	"""
	ensure_logged_in()
	user, is_view_mode = _resolve_effective_user(view_as, viewer)

	if not practice_document or not frappe.db.exists(PRACTICE_DOCUMENT_DOCTYPE, practice_document):
		frappe.throw("You do not have permission to access this document.", frappe.PermissionError)

	source = frappe.get_doc(PRACTICE_DOCUMENT_DOCTYPE, practice_document)

	if not _is_resource_reachable(source):
		frappe.throw("You do not have permission to access this document.", frappe.PermissionError)

	if not _can_user_see_resource(source.as_dict(), user=user):
		if is_view_mode or not _is_admin(user):
			frappe.throw("You do not have permission to access this document.", frappe.PermissionError)

	if not file_url:
		_serve_private_file(source.document_file)
		return

	valid_files = {row.get("file") for row in _get_additional_files(source)}

	if file_url not in valid_files:
		frappe.throw("You do not have permission to access this file.", frappe.PermissionError)

	_serve_private_file(file_url)


@frappe.whitelist()
def get_my_document_file(requirement_name, file_url=None, view_as=None, viewer=None):
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
	requirement = _get_owned_requirement(requirement_name, view_as=view_as, viewer=viewer)

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


def _get_owned_requirement(requirement_name, view_as=None, viewer=None):
	ensure_logged_in()
	user, is_view_mode = _resolve_effective_user(view_as, viewer)

	if not requirement_name or not frappe.db.exists(COACH_DOCUMENT_REQUIREMENT_DOCTYPE, requirement_name):
		frappe.throw("You do not have permission to access this document.", frappe.PermissionError)

	requirement = frappe.get_doc(COACH_DOCUMENT_REQUIREMENT_DOCTYPE, requirement_name)

	if requirement.user != user:
		if is_view_mode or not _is_admin(user):
			frappe.throw("You do not have permission to access this document.", frappe.PermissionError)

	return requirement


@frappe.whitelist()
def get_my_document_requirement(requirement_name, view_as=None, viewer=None):
	"""
	Everything the in-dashboard "Open Document" view needs: the
	requirement itself, plus the document text/purpose that only live on
	the linked Practice Document (never duplicated onto the requirement's
	own snapshot fields).
	"""
	requirement = _get_owned_requirement(requirement_name, view_as=view_as, viewer=viewer)
	data = requirement.as_dict()

	if requirement.practice_document and frappe.db.exists(PRACTICE_DOCUMENT_DOCTYPE, requirement.practice_document):
		source = frappe.get_doc(PRACTICE_DOCUMENT_DOCTYPE, requirement.practice_document)
	else:
		source = None

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


def _get_practice_document_brand_values(doc):
	return {
		brand_value
		for fieldname, brand_value in PRACTICE_DOCUMENT_BRAND_FIELDS.items()
		if doc.meta.has_field(fieldname) and doc.get(fieldname)
	}


def _get_coach_names_with_brand_access(brand_values):
	if not brand_values or not frappe.db.exists("DocType", "Coach Brand Access"):
		return set()

	return set(frappe.get_all(
		"Coach Brand Access",
		filters={"brand_access": ["in", list(brand_values)], "parenttype": "Coach"},
		pluck="parent",
	))


def _get_session_worker_names_with_brand_access(brand_values):
	if not brand_values or not frappe.db.exists("DocType", "Session Worker Brand Access"):
		return set()

	return set(frappe.get_all(
		"Session Worker Brand Access",
		filters={"brand_access": ["in", list(brand_values)], "parenttype": "Session Worker"},
		pluck="parent",
	))


def _get_item_access_gated_coach_names(practice_document_name):
	"""
	None if this Practice Document has no Linked Items, meaning Brand-Based
	Access applies without restriction. Otherwise the set of coaches who
	currently have Item Access to at least one of them - Brand-Based
	Access must be intersected with this, so a document tied to a
	specific item never becomes visible to a brand-matched coach who
	isn't actually entitled to sell/run that item. There's no equivalent
	Item Access concept for Session Workers in this app, so this
	restriction only ever narrows the coach side.
	"""
	linked_item_codes = _get_linked_item_codes(practice_document_name)
	if not linked_item_codes:
		return None

	return _get_coach_names_with_access_to_items(linked_item_codes)


def _ensure_brand_requirement(practice_document_name, person_type, person_name, user):
	if not user:
		return

	payload = {
		"doctype": COACH_DOCUMENT_REQUIREMENT_DOCTYPE,
		"person_type": person_type,
		"user": user,
		"practice_document": practice_document_name,
		"granted_via_brand_access": 1,
	}
	if person_type == "Coach":
		payload["coach"] = person_name
	else:
		payload["session_worker"] = person_name

	frappe.get_doc(payload).insert(ignore_permissions=True)


def _sync_brand_document_requirements(practice_document_name, brand_values):
	"""
	Internal Compliance/Both half of brand-based access (never applies to
	a Workshop Resource - see _resync_practice_document_brand_access)-
	reconciles Coach Document Requirement rows against who currently has
	matching Brand Access (Coach Brand Access and Session Worker Brand
	Access), adding missing rows and removing only the ones this same
	mechanism added (its own granted_via_brand_access flag). A row is
	only ever removed while still a draft (docstatus 0) -
	a completed or cancelled requirement is a historical record of what
	was actually agreed to, and is never touched regardless of what brand
	access now says.
	"""
	item_access_gate = _get_item_access_gated_coach_names(practice_document_name)

	coach_names = _get_coach_names_with_brand_access(brand_values)
	if item_access_gate is not None:
		coach_names = coach_names & item_access_gate

	session_worker_names = _get_session_worker_names_with_brand_access(brand_values)

	target = {("Coach", name) for name in coach_names} | {("Session Worker", name) for name in session_worker_names}

	existing_rows = frappe.get_all(
		COACH_DOCUMENT_REQUIREMENT_DOCTYPE,
		filters={"practice_document": practice_document_name},
		fields=["name", "person_type", "coach", "session_worker", "granted_via_brand_access", "docstatus"],
	)

	covered = set()

	for row in existing_rows:
		person_type = row.get("person_type")
		person_name = row.get("coach") if person_type == "Coach" else row.get("session_worker")
		key = (person_type, person_name)

		if person_name:
			covered.add(key)

		if row.get("granted_via_brand_access") and key not in target and row.get("docstatus") == 0:
			frappe.delete_doc(COACH_DOCUMENT_REQUIREMENT_DOCTYPE, row.get("name"), ignore_permissions=True)

	for person_type, person_name in target - covered:
		try:
			user = _get_coach_login(person_name) if person_type == "Coach" else _get_session_worker_login(person_name)
			_ensure_brand_requirement(practice_document_name, person_type, person_name, user)
		except Exception:
			frappe.log_error(
				frappe.get_traceback(),
				f"Brand Document Requirement Sync Failed - {practice_document_name} - {person_type} - {person_name}",
			)


def _resync_practice_document_brand_access(practice_document_name):
	"""
	Dispatches brand-based access to whichever mechanism this document
	actually uses:

	- Workshop Resource (document_type) is ALWAYS purely a resource,
	  regardless of Document Purpose (which deliberately stays Internal
	  Compliance for these, per _is_resource_reachable) - it must never
	  also get a Coach Document Requirement, or the same document shows
	  up twice on a coach's Documents page (once as a requirement, once
	  as a resource).
	- Internal Compliance/Both (and not a Workshop Resource) creates/
	  removes Coach Document Requirements.
	- Client Resource/Both (or a Workshop Resource) reconciles Available
	  to Coaches - via item_access._resync_practice_document_coaches,
	  which is now the single place Item Access and Brand Access are
	  reconciled together, so a coach entitled through either route keeps
	  access and is only dropped once neither applies.
	"""
	doc = frappe.get_doc(PRACTICE_DOCUMENT_DOCTYPE, practice_document_name)
	brand_values = _get_practice_document_brand_values(doc)
	is_workshop_resource = doc.document_type == "Workshop Resource"

	if not is_workshop_resource and doc.document_purpose in ("Internal Compliance", "Both"):
		_sync_brand_document_requirements(practice_document_name, brand_values)

	if is_workshop_resource or doc.document_purpose in ("Client Resource", "Both"):
		from dashboard.api.shared.item_access import _resync_practice_document_coaches
		_resync_practice_document_coaches(practice_document_name)


def sync_practice_document_brand_requirements(doc, method=None):
	"""
	Practice Document.on_update hook - ticking or unticking one of the
	Brand Access checkboxes (shown regardless of Document Purpose, so
	this works for Client Resource documents too) adds or removes access
	for everyone connected to that brand (Coach Brand Access / Session
	Worker Brand Access): for Internal Compliance/Both that's a Coach
	Document Requirement, for Client Resource/Both that's a row in
	Available to Coaches. See sync_coach_brand_document_requirements /
	sync_session_worker_brand_document_requirements for the other half -
	a person's own brand access changing.
	"""
	if not doc.name:
		return

	try:
		_resync_practice_document_brand_access(doc.name)
	except Exception:
		frappe.log_error(frappe.get_traceback(), f"Practice Document Brand Requirement Sync Failed - {doc.name}")


def _get_practice_documents_needing_brand_resync(person_type, person_name, matching_fieldnames):
	"""
	Every Practice Document that might need re-checking for this one
	person: documents whose ticked brands currently overlap their Brand
	Access (potential adds), plus documents where they already hold a
	brand-granted row (potential removes, e.g. a brand was just taken off
	their record). Each candidate is then resynced from its OWN current
	brand fields (not the person's), so a document tagged with more than
	one brand isn't wrongly narrowed to just the brand that changed.
	"""
	candidate_names = set()

	if matching_fieldnames:
		candidate_names |= set(frappe.get_all(
			PRACTICE_DOCUMENT_DOCTYPE,
			or_filters={fieldname: 1 for fieldname in matching_fieldnames},
			pluck="name",
		))

	person_filters = {"granted_via_brand_access": 1}
	if person_type == "Coach":
		person_filters["coach"] = person_name
	else:
		person_filters["session_worker"] = person_name

	candidate_names |= set(frappe.get_all(
		COACH_DOCUMENT_REQUIREMENT_DOCTYPE, filters=person_filters, pluck="practice_document",
	))

	if person_type == "Coach":
		candidate_names |= set(frappe.get_all(
			PRACTICE_DOCUMENT_COACH_DOCTYPE,
			filters={"coach": person_name, "granted_via_brand_access": 1, "parenttype": PRACTICE_DOCUMENT_DOCTYPE},
			pluck="parent",
		))

	return candidate_names


def _sync_person_brand_document_access(brand_access_doctype, person_type, person_name):
	if not frappe.db.exists("DocType", brand_access_doctype):
		return

	person_brand_values = set(frappe.get_all(
		brand_access_doctype,
		filters={"parent": person_name, "parenttype": person_type},
		pluck="brand_access",
	))

	practice_document_meta = frappe.get_meta(PRACTICE_DOCUMENT_DOCTYPE)
	matching_fieldnames = [
		fieldname
		for fieldname, brand_value in PRACTICE_DOCUMENT_BRAND_FIELDS.items()
		if brand_value in person_brand_values and practice_document_meta.has_field(fieldname)
	]

	for practice_document_name in _get_practice_documents_needing_brand_resync(person_type, person_name, matching_fieldnames):
		try:
			_resync_practice_document_brand_access(practice_document_name)
		except Exception:
			frappe.log_error(
				frappe.get_traceback(), f"Brand Document Access Sync Failed - {practice_document_name} - {person_type} - {person_name}",
			)


def sync_coach_brand_document_requirements(doc, method=None):
	"""
	Coach.on_update hook - companion to
	sync_practice_document_brand_requirements above. Coach Brand Access is
	a child table on Coach, so it has no on_update of its own; this fires
	whenever the Coach record (and so their Brand Access rows) is saved -
	adding a brand (e.g. becoming a People franchisee) grants access to
	every Practice Document already tagged with it, and removing one
	takes access away again (subject to the same "never touch a completed
	requirement" rule as the document side).
	"""
	if not doc.name:
		return

	try:
		_sync_person_brand_document_access("Coach Brand Access", "Coach", doc.name)
	except Exception:
		frappe.log_error(frappe.get_traceback(), f"Coach Brand Requirement Sync Failed - {doc.name}")


def sync_session_worker_brand_document_requirements(doc, method=None):
	"""
	Session Worker.on_update hook - the Session Worker equivalent of
	sync_coach_brand_document_requirements above, via a "Session Worker
	Brand Access" child table assumed to mirror Coach Brand Access's
	shape (brand_access field, same options). Guarded by
	frappe.db.exists() in _sync_person_brand_document_access, so this is
	a silent no-op rather than an error if that doctype doesn't exist or
	is named differently on this site.
	"""
	if not doc.name:
		return

	try:
		_sync_person_brand_document_access("Session Worker Brand Access", "Session Worker", doc.name)
	except Exception:
		frappe.log_error(frappe.get_traceback(), f"Session Worker Brand Requirement Sync Failed - {doc.name}")
