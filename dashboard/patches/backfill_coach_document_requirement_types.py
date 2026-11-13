"""
"all the documents are stil not showing - i do see under other there
is 31 but it looks like th policies and procedures that should be
under the policy and procedure tabs" - the real bug: _ensure_brand_
requirement (practice_documents.py) never set document_type when
creating a Coach Document Requirement row via Brand-Based Access, for
either a coach or a session worker - get_my_documents_by_type then has
no real Document Type to match against a tab, so every one of these
rows silently bucketed into "Other" instead of its actual Policy/
Procedure/etc tab. Fixed at the source in _ensure_brand_requirement;
this backfills every row that already exists with the real value off
its own linked Practice Document.

Safe to re-run - only ever touches a row whose document_type is
currently blank.
"""

import frappe


def execute():
	if not frappe.db.exists("DocType", "Coach Document Requirement"):
		return

	rows = frappe.get_all(
		"Coach Document Requirement",
		filters={"document_type": ["in", ["", None]]},
		fields=["name", "practice_document"],
	)

	if not rows:
		return

	practice_document_names = {row.practice_document for row in rows if row.practice_document}

	document_types = {}
	if practice_document_names:
		document_types = {
			pd.name: pd.document_type
			for pd in frappe.get_all(
				"Practice Document",
				filters={"name": ["in", list(practice_document_names)]},
				fields=["name", "document_type"],
			)
		}

	updated = 0
	for row in rows:
		document_type = document_types.get(row.practice_document)
		if document_type:
			frappe.db.set_value("Coach Document Requirement", row.name, "document_type", document_type)
			updated += 1

	if updated:
		frappe.db.commit()
