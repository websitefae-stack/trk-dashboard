"""
Practice Document -> Coach Document Requirement assignment, and the coach
Client Resources library.

Practice Document has three purposes:
- Internal Compliance: only a Coach Document Requirement is created (what
  the coach must do internally). Never appears in Client Resources.
- Client Resource: only appears in the coach's Client Resources library
  (what the coach can share with a client). No Coach Document Requirement
  is created.
- Both: both of the above happen for the same document.

sync_coach_document_requirements() is called from Practice Document's
on_update() and keeps Coach Document Requirement rows in sync without ever
destroying a coach's existing progress on one - a requirement is only
created when a coach is newly in scope, and only deleted when a coach
drops out of scope (purpose changed away from compliance, status is no
longer Published, or that coach was removed from Selected People or
Roles). Requirements for coaches still in scope are left alone except for
the read-only fields copied from the Practice Document itself.
"""

import frappe
from frappe import _

from dashboard.api.shared.permissions import (
	ensure_logged_in,
	is_office_user,
	get_current_coach_name,
)

PRACTICE_DOCUMENT_DOCTYPE = "Practice Document"
COACH_DOCUMENT_REQUIREMENT_DOCTYPE = "Coach Document Requirement"

LIBRARY_FIELDS = [
	"name",
	"document_title",
	"document_code",
	"version",
	"document_type",
	"summary",
	"category",
	"shareable_with",
	"client_action_required",
	"sharing_instructions",
	"sharing_method",
	"attached_file",
	"document_purpose",
	"all_coaches",
]


# ---------------------------------------------------------------------------
# Assignment (Practice Document -> Coach Document Requirement)
# ---------------------------------------------------------------------------

def _resolve_target_coaches(doc):
	if doc.get("all_coaches"):
		return set(frappe.get_all("Coach", pluck="name", ignore_permissions=True))

	return {row.coach for row in (doc.get("selected_people_or_roles") or []) if row.coach}


def sync_coach_document_requirements(doc):
	creates_requirements = doc.status == "Published" and doc.document_purpose in (
		"Internal Compliance",
		"Both",
	)

	target_coaches = _resolve_target_coaches(doc) if creates_requirements else set()

	existing = frappe.get_all(
		COACH_DOCUMENT_REQUIREMENT_DOCTYPE,
		filters={"practice_document": doc.name},
		fields=["name", "coach"],
		ignore_permissions=True,
	)
	existing_by_coach = {row.coach: row.name for row in existing}

	for coach_name in target_coaches:
		if coach_name in existing_by_coach:
			frappe.db.set_value(
				COACH_DOCUMENT_REQUIREMENT_DOCTYPE,
				existing_by_coach[coach_name],
				{
					"document_title": doc.document_title,
					"document_code": doc.document_code,
					"document_version": doc.version,
					"mandatory": doc.mandatory,
				},
			)
			continue

		requirement = frappe.new_doc(COACH_DOCUMENT_REQUIREMENT_DOCTYPE)
		requirement.practice_document = doc.name
		requirement.coach = coach_name
		requirement.document_title = doc.document_title
		requirement.document_code = doc.document_code
		requirement.document_version = doc.version
		requirement.mandatory = doc.mandatory
		requirement.status = "Pending"
		requirement.insert(ignore_permissions=True)

	for coach_name, requirement_name in existing_by_coach.items():
		if coach_name not in target_coaches:
			frappe.delete_doc(
				COACH_DOCUMENT_REQUIREMENT_DOCTYPE,
				requirement_name,
				ignore_permissions=True,
				force=True,
			)


# ---------------------------------------------------------------------------
# Client Resources library (coach-facing)
# ---------------------------------------------------------------------------

def coach_can_see_resource(row, coach_name):
	if row.get("all_coaches"):
		return True

	if not coach_name:
		return False

	selected = frappe.get_all(
		"Practice Document Coach",
		filters={"parent": row["name"], "parenttype": PRACTICE_DOCUMENT_DOCTYPE},
		pluck="coach",
		ignore_permissions=True,
	)

	return coach_name in selected


def _split_categories(category_text):
	if not category_text:
		return []

	seen = []
	for part in category_text.split(","):
		label = part.strip()
		if label and label not in seen:
			seen.append(label)

	return seen


def get_visible_client_resources(coach_name=None):
	"""
	Published Practice Documents whose purpose includes Client Resource,
	restricted to whichever coaches are allowed to see each one.
	"""
	ensure_logged_in()

	rows = frappe.get_all(
		PRACTICE_DOCUMENT_DOCTYPE,
		filters={
			"status": "Published",
			"document_purpose": ["in", ["Client Resource", "Both"]],
		},
		fields=LIBRARY_FIELDS,
		order_by="modified desc",
		ignore_permissions=True,
	)

	if is_office_user():
		visible = rows
	else:
		coach_name = coach_name or get_current_coach_name(optional=True)
		visible = [row for row in rows if coach_can_see_resource(row, coach_name)]

	for row in visible:
		row["categories"] = _split_categories(row.get("category"))

	return visible


@frappe.whitelist()
def get_client_resource_library():
	return get_visible_client_resources()


@frappe.whitelist()
def get_client_resources_summary():
	"""
	Powers the "Client Resources" card on /coach_db: a count, the most
	recently published resources, and the set of categories in use.
	"""
	ensure_logged_in()

	resources = get_visible_client_resources()

	categories = []
	for row in resources:
		for label in row["categories"]:
			if label not in categories:
				categories.append(label)

	return {
		"total_resources": len(resources),
		"recent_resources": [
			{"name": row["name"], "document_title": row["document_title"]}
			for row in resources[:5]
		],
		"categories": categories,
	}


@frappe.whitelist()
def get_practice_document_file(practice_document_name):
	"""
	A coach browsing their Client Resources library isn't a System Manager,
	so a private attachment's own file URL would 403 for them directly -
	this proxies the download after checking the same library-visibility
	rules as the library listing itself.
	"""
	resources = get_visible_client_resources()
	match = next((row for row in resources if row["name"] == practice_document_name), None)

	if not match:
		frappe.throw(_("You do not have access to this document."), frappe.PermissionError)

	if not match.get("attached_file"):
		frappe.throw(_("No file is attached to this document."))

	from frappe.utils.file_manager import get_file

	fname, fcontent = get_file(match["attached_file"])

	frappe.local.response.filename = fname
	frappe.local.response.filecontent = fcontent
	frappe.local.response.type = "download"


# ---------------------------------------------------------------------------
# "My Documents" (coach-facing compliance view)
# ---------------------------------------------------------------------------

STATUS_ORDER = ["Pending", "Acknowledged", "Completed"]


def _get_owned_requirement(requirement_name):
	ensure_logged_in()

	if not requirement_name or not frappe.db.exists(COACH_DOCUMENT_REQUIREMENT_DOCTYPE, requirement_name):
		frappe.throw(_("You do not have permission to access this document."), frappe.PermissionError)

	requirement = frappe.get_doc(COACH_DOCUMENT_REQUIREMENT_DOCTYPE, requirement_name)

	if is_office_user():
		return requirement

	coach_name = get_current_coach_name(optional=True)

	if not coach_name or requirement.coach != coach_name:
		frappe.throw(_("You do not have permission to access this document."), frappe.PermissionError)

	return requirement


@frappe.whitelist()
def get_my_document_requirements():
	ensure_logged_in()

	coach_name = get_current_coach_name(optional=True)
	if not coach_name:
		return []

	rows = frappe.get_all(
		COACH_DOCUMENT_REQUIREMENT_DOCTYPE,
		filters={"coach": coach_name},
		fields=[
			"name", "practice_document", "document_title", "document_code",
			"document_version", "mandatory", "status", "assigned_on", "completed_on",
		],
		order_by="assigned_on desc",
		ignore_permissions=True,
	)

	practice_document_names = list({row.practice_document for row in rows if row.practice_document})
	details_by_name = {}

	if practice_document_names:
		for pd in frappe.get_all(
			PRACTICE_DOCUMENT_DOCTYPE,
			filters={"name": ["in", practice_document_names]},
			fields=["name", "attached_file", "summary", "category", "document_type"],
			ignore_permissions=True,
		):
			details_by_name[pd.name] = pd

	for row in rows:
		details = details_by_name.get(row.practice_document) or {}
		row["has_file"] = bool(details.get("attached_file"))
		row["summary"] = details.get("summary")
		row["document_type"] = details.get("document_type")
		row["categories"] = _split_categories(details.get("category"))

	return rows


@frappe.whitelist()
def get_my_document_summary():
	"""
	Powers the "My Documents" card on /coach_db and its sidebar badge -
	mirrors get_client_resources_summary()'s shape/purpose but for the
	coach's own Coach Document Requirements rather than the shared library.
	Returns all zeros for anyone who isn't a coach (franchisor/session
	worker dashboards never show this card, but the sidebar badge loader
	runs on every page and should just quietly do nothing for them).
	"""
	ensure_logged_in()

	coach_name = get_current_coach_name(optional=True)

	if not coach_name:
		return {"outstanding": 0, "completed": 0, "total": 0, "recent_outstanding": []}

	rows = frappe.get_all(
		COACH_DOCUMENT_REQUIREMENT_DOCTYPE,
		filters={"coach": coach_name},
		fields=["name", "document_title", "status"],
		order_by="assigned_on desc",
		ignore_permissions=True,
	)

	outstanding = [row for row in rows if row.status != "Completed"]
	completed = [row for row in rows if row.status == "Completed"]

	return {
		"outstanding": len(outstanding),
		"completed": len(completed),
		"total": len(rows),
		"recent_outstanding": [
			{"name": row.name, "document_title": row.document_title}
			for row in outstanding[:5]
		],
	}


@frappe.whitelist()
def get_my_document_file(requirement_name):
	"""
	Same private-attachment proxy technique as get_practice_document_file(),
	scoped by ownership of the Coach Document Requirement instead of Client
	Resources library visibility.
	"""
	requirement = _get_owned_requirement(requirement_name)

	if not requirement.practice_document:
		frappe.throw(_("No document is attached."))

	attached_file = frappe.db.get_value(PRACTICE_DOCUMENT_DOCTYPE, requirement.practice_document, "attached_file")

	if not attached_file:
		frappe.throw(_("No file is attached to this document."))

	from frappe.utils.file_manager import get_file

	fname, fcontent = get_file(attached_file)

	frappe.local.response.filename = fname
	frappe.local.response.filecontent = fcontent
	frappe.local.response.type = "download"


@frappe.whitelist()
def update_my_document_status(requirement_name, status):
	"""
	Moves a Coach Document Requirement forward through Pending ->
	Acknowledged -> Completed - never backward, never skipping past
	Completed. Uses requirement.save(), never frappe.db.set_value, so the
	doctype's own validate() (coach_document_requirement.py) is what sets
	completed_on - this never re-implements that.
	"""
	requirement = _get_owned_requirement(requirement_name)

	if status not in ("Acknowledged", "Completed"):
		frappe.throw(_("Invalid status."))

	if requirement.status == "Completed":
		frappe.throw(_("This document has already been completed."))

	current_index = STATUS_ORDER.index(requirement.status) if requirement.status in STATUS_ORDER else 0

	if STATUS_ORDER.index(status) <= current_index:
		frappe.throw(_("This document is already at or past that status."))

	requirement.status = status
	requirement.save(ignore_permissions=True)
	frappe.db.commit()

	return {"ok": True, "status": requirement.status, "completed_on": requirement.completed_on}
