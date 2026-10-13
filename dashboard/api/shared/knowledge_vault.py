"""
Franchisor-facing "Knowledge Vault" content admin - lets office/Ashley
build a library of training videos/PDFs/images/documents, decide which
School organisations get access to each one at all, and narrow each one
further to specific staff Roles and/or Year Groups within those schools.

Three gates, all of which a staff member must clear to see a resource
(see get_knowledge_vault_resources_for_school_staff() below, the one
function school_dashboard actually calls):

1. Their own Organisation Membership has can_access_knowledge_vault
   ticked (client_portal's existing master on/off switch - unchanged by
   this module, checked by the caller before it ever reaches here).
2. Their school is one of the resource's allocated_schools.
3. Their own Role/Year Group match the resource's target_roles/
   target_year_groups (each blank = no restriction on that dimension).

target_roles/target_year_groups are stored as JSON arrays in plain Small
Text fields (see create_knowledge_vault_doctypes.py's own docstring for
why this isn't a Table MultiSelect) - every function here that reads or
writes them does so as a real Python list, never raw JSON, so nothing
outside this module needs to know that detail.
"""

import json

import frappe
from frappe import _
from werkzeug.utils import secure_filename

from dashboard.api.shared.permissions import is_franchisor_user
from dashboard.api.shared.utils import coalesce_str, coalesce_raw

RESOURCE_DOCTYPE = "Knowledge Vault Resource"
RESOURCE_SCHOOL_DOCTYPE = "Knowledge Vault Resource School"

RESOURCE_TYPE_OPTIONS = ["Video", "PDF", "Image", "Document", "Email Template", "Instructions", "Other"]

# Same lists school_dashboard's own school.py defines for the staff-invite
# Role/Year Group selects - duplicated rather than cross-imported, same
# light-coupling already used between these sibling apps elsewhere.
SCHOOL_ROLE_OPTIONS = [
    "Head", "Senior Leader", "Teacher", "Teaching Assistant",
    "SENCO", "Pastoral Staff", "School Administrator", "Other",
]

YEAR_GROUP_OPTIONS = [
    "Whole School", "Reception", "Year 1", "Year 2", "Year 3",
    "Year 4", "Year 5", "Year 6", "Other",
]


def _ensure_franchisor():
    if not is_franchisor_user():
        frappe.throw(_("Only the franchisor can manage the Knowledge Vault."), frappe.PermissionError)


def _parse_list(value):
    if isinstance(value, list):
        return [v for v in value if v]

    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return [v for v in parsed if v] if isinstance(parsed, list) else []
        except Exception:
            return []

    return []


@frappe.whitelist()
def get_knowledge_vault_options():
    """Role/Year Group/Resource Type choices for the admin page's forms -
    one call so the page never has three separate round trips just to
    populate some selects."""
    _ensure_franchisor()

    return {
        "role_options": SCHOOL_ROLE_OPTIONS,
        "year_group_options": YEAR_GROUP_OPTIONS,
        "resource_type_options": RESOURCE_TYPE_OPTIONS,
    }


@frappe.whitelist()
def get_knowledge_vault_school_options():
    """Every School already granted a portal licence - the only schools
    it makes sense to allocate a resource to (a school with no licence
    has nobody who could ever log in and see it)."""
    _ensure_franchisor()

    from dashboard.api.shared.school_licenses import get_school_licenses

    return [
        {"customer": row["customer"], "label": row["client_name"] or row["customer"]}
        for row in get_school_licenses()
    ]


def _resource_row(doc):
    schools = [row.school for row in (doc.allocated_schools or [])]

    return {
        "name": doc.name,
        "title": doc.title,
        "description": doc.description or "",
        "resource_type": doc.resource_type or "",
        "file": doc.file or "",
        "video_url": doc.video_url or "",
        "text_content": doc.get("text_content") or "",
        "is_active": bool(doc.is_active),
        "target_roles": _parse_list(doc.target_roles),
        "target_year_groups": _parse_list(doc.target_year_groups),
        "allocated_schools": schools,
        "allocated_school_count": len(schools),
        "modified": str(doc.modified or ""),
    }


@frappe.whitelist()
def get_knowledge_vault_resources():
    _ensure_franchisor()

    names = frappe.get_all(RESOURCE_DOCTYPE, pluck="name", order_by="modified desc")
    return [_resource_row(frappe.get_doc(RESOURCE_DOCTYPE, name)) for name in names]


@frappe.whitelist()
def get_knowledge_vault_resource(name=None):
    _ensure_franchisor()

    name = coalesce_str("name", name)
    if not name or not frappe.db.exists(RESOURCE_DOCTYPE, name):
        frappe.throw(_("Resource not found."))

    return _resource_row(frappe.get_doc(RESOURCE_DOCTYPE, name))


@frappe.whitelist()
def save_knowledge_vault_resource(
    name=None, title=None, description=None, resource_type=None, video_url=None, text_content=None,
    is_active=1, target_roles=None, target_year_groups=None, allocated_schools=None,
):
    _ensure_franchisor()

    name = coalesce_str("name", name)
    title = coalesce_str("title", title)
    if not title:
        frappe.throw(_("Please enter a title."))

    resource_type = coalesce_str("resource_type", resource_type) or "Video"
    if resource_type not in RESOURCE_TYPE_OPTIONS:
        frappe.throw(_("Invalid resource type."))

    if isinstance(target_roles, str):
        target_roles = frappe.parse_json(target_roles) if target_roles else []
    if isinstance(target_year_groups, str):
        target_year_groups = frappe.parse_json(target_year_groups) if target_year_groups else []
    if isinstance(allocated_schools, str):
        allocated_schools = frappe.parse_json(allocated_schools) if allocated_schools else []

    target_roles = [r for r in (target_roles or []) if r in SCHOOL_ROLE_OPTIONS]
    target_year_groups = [y for y in (target_year_groups or []) if y in YEAR_GROUP_OPTIONS]
    allocated_schools = [s for s in (allocated_schools or []) if s and frappe.db.exists("Customer", s)]

    if name and frappe.db.exists(RESOURCE_DOCTYPE, name):
        doc = frappe.get_doc(RESOURCE_DOCTYPE, name)
    else:
        doc = frappe.new_doc(RESOURCE_DOCTYPE)

    doc.title = title
    doc.description = coalesce_str("description", description) or ""
    doc.resource_type = resource_type
    doc.video_url = coalesce_str("video_url", video_url) or ""
    doc.set("text_content", coalesce_str("text_content", text_content) or "")
    doc.is_active = 1 if int(coalesce_raw("is_active", is_active) or 0) else 0
    doc.target_roles = json.dumps(target_roles) if target_roles else ""
    doc.target_year_groups = json.dumps(target_year_groups) if target_year_groups else ""

    doc.set("allocated_schools", [])
    for school in allocated_schools:
        doc.append("allocated_schools", {"school": school})

    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return _resource_row(doc)


@frappe.whitelist()
def upload_knowledge_vault_resource_file(name=None):
    """Public (is_private=0) - same reasoning as every other file this app
    attaches to its own records (see e.g. recruitment_leads.py's own
    upload_contract_territory_map): an unguessable URL is this app's
    established security model for this class of file, and a genuinely
    private file would need its own custom permission hook to be
    viewable at all from a different app's own session (School
    Dashboard), which nothing here is set up for."""
    _ensure_franchisor()

    name = coalesce_str("name", name)
    if not name or not frappe.db.exists(RESOURCE_DOCTYPE, name):
        frappe.throw(_("Resource not found - save it once before attaching a file."))

    uploaded = frappe.request.files.get("file") if frappe.request else None
    if not uploaded:
        frappe.throw(_("No file was uploaded."))

    file_doc = frappe.get_doc({
        "doctype": "File",
        "file_name": secure_filename(uploaded.filename or "resource-file"),
        "attached_to_doctype": RESOURCE_DOCTYPE,
        "attached_to_name": name,
        "attached_to_field": "file",
        "is_private": 0,
        "content": uploaded.stream.read(),
    })
    file_doc.insert(ignore_permissions=True)

    frappe.db.set_value(RESOURCE_DOCTYPE, name, "file", file_doc.file_url)
    frappe.db.commit()

    return {"ok": True, "url": file_doc.file_url}


@frappe.whitelist()
def delete_knowledge_vault_resource(name=None):
    _ensure_franchisor()

    name = coalesce_str("name", name)
    if not name or not frappe.db.exists(RESOURCE_DOCTYPE, name):
        frappe.throw(_("Resource not found."))

    frappe.delete_doc(RESOURCE_DOCTYPE, name, ignore_permissions=True)
    frappe.db.commit()

    return {"ok": True}


def get_knowledge_vault_resources_for_school_staff(organisation, role=None, year_group=None):
    """The one function school_dashboard actually calls (via a thin
    wrapper in its own api/school.py) - organisation/role/year_group are
    already-resolved values from the caller's own Organisation
    Membership lookup (ensure_organisation_access), never trusted from
    raw request input, since this has no login check of its own.

    A resource matches when: it's active, this organisation is one of
    its allocated_schools, AND (its target_roles is empty OR role is in
    it) AND (its target_year_groups is empty OR year_group is in it).
    Both conditions use AND, not OR, deliberately - a resource targeted
    at both "Teaching Assistant" and "Year 2" is for a Year 2 Teaching
    Assistant specifically, not for every Teaching Assistant at the
    school regardless of year group, nor every Year 2 staff member
    regardless of role (see this module's own docstring)."""
    if not organisation:
        return []

    resource_names = set()
    for row in frappe.get_all(RESOURCE_SCHOOL_DOCTYPE, filters={"school": organisation}, fields=["parent"]):
        resource_names.add(row.parent)

    if not resource_names:
        return []

    docs = frappe.get_all(
        RESOURCE_DOCTYPE,
        filters={"name": ["in", list(resource_names)], "is_active": 1},
        fields=["name", "title", "description", "resource_type", "file", "video_url", "text_content", "target_roles", "target_year_groups", "modified"],
        order_by="modified desc",
    )

    results = []
    for row in docs:
        roles = _parse_list(row.target_roles)
        year_groups = _parse_list(row.target_year_groups)

        if roles and role not in roles:
            continue
        if year_groups and year_group not in year_groups:
            continue

        results.append({
            "name": row.name,
            "title": row.title,
            "description": row.description or "",
            "resource_type": row.resource_type or "",
            "file": row.file or "",
            "video_url": row.video_url or "",
            "text_content": row.get("text_content") or "",
        })

    return results
