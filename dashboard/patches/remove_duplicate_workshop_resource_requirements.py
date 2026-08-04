"""
Workshop Resource documents should only ever grant access via Available
to Coaches (Item Access / Brand-Based Access) - never a Coach Document
Requirement. A dispatch bug (fixed in
practice_documents._resync_practice_document_brand_access) was creating
both at once, which showed up as the same workshop resource appearing
twice on a coach's Documents page. This removes the leftover
requirements the bug already created. Only ever deletes a still-open
one (docstatus 0) - a completed/signed requirement is left exactly as
it is, as a historical record of what was actually agreed to.
"""

import frappe


def execute():
	if not frappe.db.exists("DocType", "Coach Document Requirement") or not frappe.db.exists("DocType", "Practice Document"):
		return

	if not frappe.get_meta("Practice Document").has_field("document_type"):
		return

	workshop_resource_names = frappe.get_all(
		"Practice Document",
		filters={"document_type": "Workshop Resource"},
		pluck="name",
	)

	if not workshop_resource_names:
		return

	stale_requirement_names = frappe.get_all(
		"Coach Document Requirement",
		filters={"practice_document": ["in", workshop_resource_names], "docstatus": 0},
		pluck="name",
	)

	for name in stale_requirement_names:
		try:
			frappe.delete_doc("Coach Document Requirement", name, ignore_permissions=True)
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"Remove Duplicate Workshop Resource Requirement - {name}")

	frappe.db.commit()
