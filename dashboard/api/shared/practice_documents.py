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
