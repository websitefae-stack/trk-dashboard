"""
Creates the Knowledge Vault content engine - two custom DocTypes, managed
entirely through the new franchisor "Knowledge Vault" admin page (never
hand-edited in Desk, though nothing stops that):

- Knowledge Vault Resource: one piece of content (a training video, a
  PDF, an image, a document) that office/Ashley can allocate to specific
  schools and target at specific staff.
- Knowledge Vault Resource School (child table of Knowledge Vault
  Resource): which School organisations (Customer records flagged
  is_portal_organisation + organisation_type "School" - the same ones
  trk-dashboard's own School Licenses page manages) have been granted
  this resource at all. A resource with no rows here is allocated to no
  school and nobody can see it, regardless of its targeting below.

Staff-level targeting (target_roles/target_year_groups) is deliberately
NOT a child table/Table MultiSelect - it's a JSON array in a plain Small
Text field, read/written only through dashboard.api.shared.knowledge_
vault.py, the same "JSON array in a param" pattern calendar.py's own
occurrence_overrides/additional_workers already use elsewhere in this
app. Blank means "no restriction on this dimension" (matches everyone).
A staff member only ever sees a resource if BOTH their own Role is in
target_roles (or it's blank) AND their own Year Group is in target_year_
groups (or it's blank) - see get_knowledge_vault_resource_access()'s own
docstring for the full matching rule, including why this is AND rather
than OR (a resource meant only for Year 2 Teaching Assistants must not
also be visible to a Year 2 Head, or to a Teaching Assistant in Year 5).

The existing can_access_knowledge_vault flag on Organisation Membership
(client_portal) remains the master on/off switch per staff member -
this targeting is an additional, finer-grained narrowing on top of that,
not a replacement for it.

Runs automatically on the next `bench migrate` - no manual step needed.
"""

import frappe

RESOURCE_SCHOOL_DOCTYPE = "Knowledge Vault Resource School"
RESOURCE_DOCTYPE = "Knowledge Vault Resource"

RESOURCE_TYPE_OPTIONS = "Video\nPDF\nImage\nDocument\nEmail Template\nOther"


def execute():
    _create_resource_school_doctype()
    _create_resource_doctype()


def _managed_permissions():
    return [
        {
            "role": "System Manager",
            "read": 1, "write": 1, "create": 1, "delete": 1,
            "report": 1, "export": 1, "print": 1, "email": 1, "share": 1,
        },
    ]


def _create_resource_school_doctype():
    if frappe.db.exists("DocType", RESOURCE_SCHOOL_DOCTYPE):
        return

    doc = frappe.get_doc({
        "doctype": "DocType",
        "name": RESOURCE_SCHOOL_DOCTYPE,
        "module": "Dashboard",
        "custom": 1,
        "istable": 1,
        "editable_grid": 1,
        "fields": [
            {
                "fieldname": "school",
                "fieldtype": "Link",
                "options": "Customer",
                "label": "School",
                "reqd": 1,
                "in_list_view": 1,
            },
        ],
        "permissions": _managed_permissions(),
    })
    doc.insert(ignore_permissions=True)


def _create_resource_doctype():
    if frappe.db.exists("DocType", RESOURCE_DOCTYPE):
        return

    doc = frappe.get_doc({
        "doctype": "DocType",
        "name": RESOURCE_DOCTYPE,
        "module": "Dashboard",
        "custom": 1,
        "naming_rule": "Autoincrement",
        "autoname": "autoincrement",
        "fields": [
            {"fieldname": "title", "fieldtype": "Data", "label": "Title", "reqd": 1, "in_list_view": 1},
            {"fieldname": "description", "fieldtype": "Small Text", "label": "Description"},
            {"fieldname": "is_active", "fieldtype": "Check", "label": "Active", "default": "1", "in_list_view": 1},
            {"fieldname": "content_section", "fieldtype": "Section Break", "label": "Content"},
            {
                "fieldname": "resource_type",
                "fieldtype": "Select",
                "options": RESOURCE_TYPE_OPTIONS,
                "label": "Resource Type",
                "default": "Video",
                "in_list_view": 1,
            },
            {"fieldname": "file", "fieldtype": "Attach", "label": "File"},
            {
                "fieldname": "video_url",
                "fieldtype": "Data",
                "options": "URL",
                "label": "Video URL",
                "description": "A YouTube/Vimeo (or similar) link, as an alternative or addition to an uploaded file.",
            },
            {"fieldname": "targeting_section", "fieldtype": "Section Break", "label": "Who This Is For"},
            {
                "fieldname": "target_roles",
                "fieldtype": "Small Text",
                "label": "Target Roles (JSON)",
                "description": (
                    "Managed by the Knowledge Vault admin page - a JSON array of role "
                    "names (e.g. [\"Teacher\", \"Teaching Assistant\"]), or blank for "
                    "every role."
                ),
            },
            {
                "fieldname": "target_year_groups",
                "fieldtype": "Small Text",
                "label": "Target Year Groups (JSON)",
                "description": (
                    "Managed by the Knowledge Vault admin page - a JSON array of year "
                    "groups (e.g. [\"Year 1\", \"Year 2\"]), or blank for every year group."
                ),
            },
            {"fieldname": "allocation_section", "fieldtype": "Section Break", "label": "Allocated Schools"},
            {
                "fieldname": "allocated_schools",
                "fieldtype": "Table",
                "options": RESOURCE_SCHOOL_DOCTYPE,
                "label": "Allocated Schools",
                "description": "Only these schools' staff can see this resource at all, regardless of the targeting above.",
            },
        ],
        "permissions": _managed_permissions(),
        "sort_field": "modified",
        "sort_order": "DESC",
        "track_changes": 1,
    })
    doc.insert(ignore_permissions=True)
