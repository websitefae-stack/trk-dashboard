"""
Re-run of resync_practice_document_resource_access(_v2).py - a coach was
seen with access to a Workshop Resource linked to a specific service she
does not have Item Access to. Root cause: item-linked Workshop Resource
access is decided entirely by which company a coach belongs to, but
nothing resynced it when a coach's own company changed (e.g. as part of
a franchise transfer) - see item_access.sync_coach_item_access_resource_
requirements, the new Coach.on_update hook that now catches this going
forward. This patch re-runs the same reconciliation once to catch up
whoever already drifted out of sync before that hook existed.

Runs automatically on the next `bench migrate` - no manual step needed.
"""

import frappe


def execute():
	if not frappe.db.exists("DocType", "Practice Document") or not frappe.db.exists("DocType", "Practice Document Item"):
		return

	if not frappe.get_meta("Practice Document").has_field("linked_items"):
		return

	from dashboard.api.shared.item_access import resync_all_linked_item_practice_documents

	resync_all_linked_item_practice_documents("Resync Practice Document Resource Access v3")

	frappe.db.commit()
