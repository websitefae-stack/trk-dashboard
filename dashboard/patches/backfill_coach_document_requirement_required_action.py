"""
"the session workers dont have the same sign or acknolege the coaches
have on the policies and procedure. it needs to be the same for all" -
a third layer of the same _ensure_brand_requirement bug the document_type
and document_title/etc backfills already fixed (backfill_coach_document_
requirement_types.py / backfill_coach_document_requirement_details.py):
required_action, acknowledgement_declaration and signature_declaration
were never copied from the Practice Document either, so a Coach Document
Requirement row created via Brand-Based Access had nothing for
document_view's own JS to match against ('Sign' vs 'Acknowledge') -
the Acknowledge/Sign block just never showed. Session workers get
almost all of their documents through Brand-Based Access (coaches get
most of theirs through Item Access instead, a separate, unaffected
code path), so this showed up far more consistently for them, even
though any coach's own brand-based documents had exactly the same gap.

Fixed at the source in _ensure_brand_requirement (now reuses
REQUIREMENT_SNAPSHOT_FIELDS, the same practice_document_field ->
requirement_field mapping the "Prepare coach document requirement"
Server Script and sync_requirement_snapshot_fields() already use, so
this can't drift out of sync with those again); this backfills every
row that already exists.

A separate patch from the two above (already run, logged, and now a
no-op since their own blank field is no longer blank anywhere) rather
than editing either - a logged patch never re-runs even if its code
changes. Safe to re-run - only ever touches a row whose required_action
is currently blank.
"""

import frappe


def execute():
	if not frappe.db.exists("DocType", "Coach Document Requirement"):
		return

	meta = frappe.get_meta("Coach Document Requirement")
	if not meta.has_field("required_action"):
		return

	rows = frappe.get_all(
		"Coach Document Requirement",
		filters={"required_action": ["in", ["", None]]},
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
				fields=["name", "required_action", "acknowledgement_statement", "signature_statement"],
			)
		}

	updated = 0
	for row in rows:
		source = source_by_document.get(row.practice_document)
		if not source or not source.get("required_action"):
			continue

		frappe.db.set_value("Coach Document Requirement", row.name, {
			"required_action": source.get("required_action"),
			"acknowledgement_declaration": source.get("acknowledgement_statement"),
			"signature_declaration": source.get("signature_statement"),
		})
		updated += 1

	if updated:
		frappe.db.commit()
