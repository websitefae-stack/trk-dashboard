"""
"why are the document names not showing like the last one?" - the
document_type backfill (backfill_coach_document_requirement_types.py)
fixed which tab these rows land under, but _ensure_brand_requirement
was never copying document_title/document_code/document_version/
mandatory/document_file either - every Coach Document Requirement row
created via Brand-Based Access (coach or session worker) has shown up
with no name to read, just its own record name (the "25001", "25002"…
rows Ashley saw). Fixed at the source in _ensure_brand_requirement;
this backfills every row that already exists.

A separate patch from backfill_coach_document_requirement_types.py
(already run, logged, and now a no-op since document_type is no longer
blank anywhere) rather than editing it - a logged patch never re-runs
even if its code changes. Safe to re-run - only ever touches a row
whose document_title is currently blank.
"""

import frappe


def execute():
	if not frappe.db.exists("DocType", "Coach Document Requirement"):
		return

	rows = frappe.get_all(
		"Coach Document Requirement",
		filters={"document_title": ["in", ["", None]]},
		fields=["name", "practice_document"],
	)

	if not rows:
		return

	practice_document_names = {row.practice_document for row in rows if row.practice_document}

	source_by_document = {}
	if practice_document_names:
		source_by_document = {
			pd.name: pd
			for pd in frappe.get_all(
				"Practice Document",
				filters={"name": ["in", list(practice_document_names)]},
				fields=["name", "document_title", "document_code", "version", "document_type", "mandatory", "document_file"],
			)
		}

	updated = 0
	for row in rows:
		source = source_by_document.get(row.practice_document)
		if not source:
			continue

		frappe.db.set_value("Coach Document Requirement", row.name, {
			"document_title": source.get("document_title"),
			"document_code": source.get("document_code"),
			"document_version": source.get("version"),
			"document_type": source.get("document_type"),
			"mandatory": source.get("mandatory"),
			"document_file": source.get("document_file"),
		})
		updated += 1

	if updated:
		frappe.db.commit()
