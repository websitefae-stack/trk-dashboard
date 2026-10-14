"""
Adds staff_exclusions alongside the existing staff_grants (see
add_staff_grants_to_knowledge_vault_resource.py) - confirmed live: the
Manage Access screen's one checkbox per staff member is meant to be the
final word on whether they see a resource, but staff_grants on its own
can only ever ADD someone in on top of Role/Year Group targeting, never
take someone OUT who already sees it through that targeting. Unticking
such a person was a silent no-op - it looked like "doesn't save" when
really there was just no way to express "exclude this person" at all.

Same child doctype (Knowledge Vault Resource Staff) as staff_grants,
just a second Table field pointing at it - a child row's own parentfield
column ("staff_grants" vs "staff_exclusions") is what tells the two
apart, same as any doctype with two Table fields sharing one child
doctype. See get_knowledge_vault_resources_for_school_staff() and
set_resource_staff_grants() in knowledge_vault.py for how this is
actually applied and written.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

RESOURCE_DOCTYPE = "Knowledge Vault Resource"
RESOURCE_STAFF_DOCTYPE = "Knowledge Vault Resource Staff"


def execute():
    if not frappe.db.exists("DocType", RESOURCE_DOCTYPE) or not frappe.db.exists("DocType", RESOURCE_STAFF_DOCTYPE):
        return

    create_custom_fields({
        RESOURCE_DOCTYPE: [
            {
                "fieldname": "staff_exclusions",
                "fieldtype": "Table",
                "options": RESOURCE_STAFF_DOCTYPE,
                "label": "Staff Exclusions",
                "insert_after": "staff_grants",
                "description": "Explicit per-staff-member exclusions, set by a school's own admin - overrides the Target Roles/Year Groups above for anyone listed here, even if they'd otherwise match.",
            },
        ],
    }, ignore_validate=True)
    frappe.db.commit()
