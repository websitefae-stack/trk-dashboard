"""
Creates Knowledge Vault Resource View - one row per (resource, staff
member) the first time that staff member actually opens a resource's
video/file link (see knowledge_vault.py's own record_resource_view,
called from school_dashboard the moment a Video resource's link is
opened - "watched" here means "clicked play", not watched to
completion, since most of these are external YouTube/Vimeo links with
no reliable way to know how much was actually watched).

Ashley's own goal: see which videos get watched most, and by how much
of each school's own staff, to spot a topic worth a proactive workshop
offer (e.g. most of a school's staff watching the anxiety video is a
signal, not just a vanity metric).

"resource" is a plain Data field, not a Link - Knowledge Vault Resource
is an Autoincrement-named doctype, and this app's own code already hit
the quirk once (see get_knowledge_vault_resources_for_school_staff's
own comment) where its name comes back as a Python/JSON number in some
contexts and a string in others; storing/comparing it as a plain string
throughout, same as the existing child tables already do via their own
"parent" column, avoids that entirely rather than relying on a Link
field's own type coercion.

Runs automatically on the next `bench migrate` - no manual step needed.
"""

import frappe

RESOURCE_VIEW_DOCTYPE = "Knowledge Vault Resource View"


def execute():
    if frappe.db.exists("DocType", RESOURCE_VIEW_DOCTYPE):
        return

    doc = frappe.get_doc({
        "doctype": "DocType",
        "name": RESOURCE_VIEW_DOCTYPE,
        "module": "Dashboard",
        "custom": 1,
        "naming_rule": "Random",
        "autoname": "hash",
        "fields": [
            {"fieldname": "resource", "fieldtype": "Data", "label": "Resource", "reqd": 1, "in_list_view": 1, "in_standard_filter": 1},
            {"fieldname": "organisation", "fieldtype": "Link", "options": "Customer", "label": "School", "reqd": 1, "in_list_view": 1, "in_standard_filter": 1},
            {"fieldname": "membership", "fieldtype": "Link", "options": "Organisation Membership", "label": "Staff Member", "reqd": 1, "in_list_view": 1},
            {"fieldname": "viewed_at", "fieldtype": "Datetime", "label": "First Viewed", "in_list_view": 1},
        ],
        "permissions": [
            {
                "role": "System Manager",
                "read": 1, "write": 1, "create": 1, "delete": 1,
                "report": 1, "export": 1, "print": 1, "email": 1, "share": 1,
            },
        ],
        "sort_field": "viewed_at",
        "sort_order": "DESC",
    })
    doc.insert(ignore_permissions=True)
