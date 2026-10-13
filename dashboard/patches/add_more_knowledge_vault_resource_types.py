"""
Adds more options to Knowledge Vault Resource.resource_type's fixed
Select field - confirmed live: picking "Instructions" (added to this
app's own RESOURCE_TYPE_OPTIONS Python list in a previous commit, but
never to the DocType's own stored field) threw Frappe's own field
validation error ('Resource Type cannot be "Instructions". It should be
one of "Video", "PDF", ...') - updating the Python list alone was never
enough, exactly the same class of gap the Year Group "0" bug came from.
That Python list is still what drives the admin page's own dropdown and
save-time check; this is what makes the DocType's own Select field
actually accept those same values when the record is saved.

Directly edits the existing DocType document's own field (not a
"Custom Field" record, unlike Event.custom_session_type elsewhere in
this app - resource_type was defined directly in Knowledge Vault
Resource's own `fields` list at doctype-creation time, not attached
later via create_custom_fields()).

Safe to run more than once - only appends whatever's actually missing.
"""

import frappe

RESOURCE_DOCTYPE = "Knowledge Vault Resource"
NEW_OPTIONS = [
    "Video", "PDF", "Image", "Document", "Email Template",
    "Teacher Emails", "Parent Emails", "Teacher Crib Sheet", "Tools",
    "Session Summary", "Instructions", "Other",
]


def execute():
    if not frappe.db.exists("DocType", RESOURCE_DOCTYPE):
        return

    doctype_doc = frappe.get_doc("DocType", RESOURCE_DOCTYPE)
    field = next((f for f in doctype_doc.fields if f.fieldname == "resource_type"), None)
    if not field:
        return

    existing_options = [o.strip() for o in (field.options or "").split("\n") if o.strip()]
    missing = [o for o in NEW_OPTIONS if o not in existing_options]
    if not missing:
        return

    field.options = "\n".join(existing_options + missing)
    doctype_doc.save(ignore_permissions=True)
    frappe.db.commit()
