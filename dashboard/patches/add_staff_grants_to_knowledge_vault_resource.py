"""
Adds per-staff-member allocation on top of the existing school allocation
and Role/Year Group targeting - confirmed live: a school's own admin
needs to be able to hand-pick exactly which of their staff get a given
resource, not rely solely on Role/Year Group auto-matching (which stays,
unchanged, as the other way a resource can reach a staff member - see
get_knowledge_vault_resources_for_school_staff()'s own updated docstring
for the full three-way matching rule).

- Knowledge Vault Resource Staff (new child table of Knowledge Vault
  Resource): one row per staff member a resource has been explicitly
  granted to. staff_member links to Organisation Membership
  (client_portal) - cross-app Link fields on a child table work the same
  as any other Link field.
- staff_grants (new Table field on the existing Knowledge Vault
  Resource doctype): attached the same way text_content was added in
  add_text_content_to_knowledge_vault_resource.py - create_custom_fields
  works for attaching a field to a doctype that's itself fully custom.

Safe to run more than once - create_custom_fields skips any field that
already exists, and the child doctype creation checks for an existing
record first.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

RESOURCE_DOCTYPE = "Knowledge Vault Resource"
RESOURCE_STAFF_DOCTYPE = "Knowledge Vault Resource Staff"


def execute():
    _create_resource_staff_doctype()
    _add_staff_grants_field()


def _create_resource_staff_doctype():
    if frappe.db.exists("DocType", RESOURCE_STAFF_DOCTYPE):
        return

    doc = frappe.get_doc({
        "doctype": "DocType",
        "name": RESOURCE_STAFF_DOCTYPE,
        "module": "Dashboard",
        "custom": 1,
        "istable": 1,
        "editable_grid": 1,
        "fields": [
            {
                "fieldname": "staff_member",
                "fieldtype": "Link",
                "options": "Organisation Membership",
                "label": "Staff Member",
                "reqd": 1,
                "in_list_view": 1,
            },
        ],
        "permissions": [
            {
                "role": "System Manager",
                "read": 1, "write": 1, "create": 1, "delete": 1,
                "report": 1, "export": 1, "print": 1, "email": 1, "share": 1,
            },
        ],
    })
    doc.insert(ignore_permissions=True)


def _add_staff_grants_field():
    create_custom_fields({
        RESOURCE_DOCTYPE: [
            {
                "fieldname": "staff_grants",
                "fieldtype": "Table",
                "options": RESOURCE_STAFF_DOCTYPE,
                "label": "Staff Grants",
                "insert_after": "allocated_schools",
                "description": "Explicit per-staff-member grants, set by a school's own admin - on top of the Target Roles/Year Groups above, not instead of them.",
            },
        ],
    }, ignore_validate=True)
    frappe.db.commit()
