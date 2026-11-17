"""
Adds "Village" (The Resilient Village / TRV) to Coach Brand Access's
brand_access Select field options.

Coach Brand Access isn't a doctype this app owns - it (and Coach
itself) were created directly in the Frappe Desk, not via any JSON
file in this repo, so there's nothing version-controlled to edit for
it. Same mechanism as add_more_knowledge_vault_resource_types.py: this
directly edits the live DocType document's own field (not a "Custom
Field" record) - resource_type/brand_access were both defined in their
doctype's own `fields` list at doctype-creation time, not attached
later via create_custom_fields().

Ashley asked for this specifically so she can tick "Village" on her
own Coach record and give herself (not every other coach) access to
the TRV brand guidelines via a Practice Document's own new "TRV"
brand-based-access checkbox (brand_access_village on Practice Document
- see PRACTICE_DOCUMENT_BRAND_FIELDS in practice_documents.py).

Session Worker Brand Access is deliberately NOT touched here - she
only asked for Coach, for now.

Safe to run more than once - only appends whatever's actually missing.
"""

import frappe

DOCTYPE = "Coach Brand Access"
FIELDNAME = "brand_access"
NEW_OPTION = "Village"


def execute():
	if not frappe.db.exists("DocType", DOCTYPE):
		return

	doctype_doc = frappe.get_doc("DocType", DOCTYPE)
	field = next((f for f in doctype_doc.fields if f.fieldname == FIELDNAME), None)
	if not field:
		return

	existing_options = [o.strip() for o in (field.options or "").split("\n") if o.strip()]
	if NEW_OPTION in existing_options:
		return

	field.options = "\n".join(existing_options + [NEW_OPTION])
	doctype_doc.save(ignore_permissions=True)
	frappe.db.commit()
