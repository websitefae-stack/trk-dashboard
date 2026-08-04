"""
Re-run of resync_practice_document_resource_access.py - a coach was seen
still listed in a Workshop Resource's Available to Coaches after their
Item Access to the linked item was revoked, which the original patch (and
the Practice Document on_update hook that runs the same reconciliation on
every save) should already prevent. Re-running it now catches up anyone
whose removal silently failed the first time round (e.g. the known MySQL
"Truncated incorrect DECIMAL value" issue on this site's Frappe version -
see item_access._resync_practice_document_coaches's own comment), without
needing to know exactly which document(s) or when.

Runs automatically on the next `bench migrate` - no manual step needed.
"""

import frappe


def execute():
	if not frappe.db.exists("DocType", "Practice Document") or not frappe.db.exists("DocType", "Practice Document Item"):
		return

	if not frappe.get_meta("Practice Document").has_field("linked_items"):
		return

	from dashboard.api.shared.item_access import _resync_practice_document_coaches

	practice_document_names = frappe.get_all(
		"Practice Document Item",
		filters={"parenttype": "Practice Document"},
		pluck="parent",
		distinct=True,
	)

	for name in practice_document_names:
		try:
			_resync_practice_document_coaches(name)
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"Resync Practice Document Resource Access v2 - {name}")

	frappe.db.commit()
