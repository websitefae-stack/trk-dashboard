"""
Franchisor-facing "Knowledge Vault" content admin - lets office/Ashley
build a library of training videos/PDFs/images/documents, decide which
School organisations get access to each one at all, and narrow each one
further to specific staff Roles and/or Year Groups within those schools.
A school's own Primary Contact (is_primary_contact - not just anyone
with can_manage_users, which an admin can grant a colleague without
making them the Primary Contact) can additionally hand-pick specific
staff members for a resource, on top of that Role/Year Group targeting
- see get_knowledge_vault_resources_for_school_staff() and
set_resource_staff_grants() below for the full rule.

Gates a non-admin staff member must clear to see a resource (see
get_knowledge_vault_resources_for_school_staff() below, the one
function school_dashboard actually calls):

1. Their own Organisation Membership has can_access_knowledge_vault
   ticked (client_portal's existing master on/off switch - unchanged by
   this module, checked by the caller before it ever reaches here).
2. Their school is one of the resource's allocated_schools.
3. EITHER their own Role/Year Group match the resource's target_roles/
   target_year_groups (each blank = no restriction on that dimension,
   both must match when both are set) OR they're explicitly listed in
   the resource's staff_grants for their own organisation - confirmed
   live: a school's admin needs to hand-pick specific people on top of
   (not instead of) the broad Role/Year Group rule, since not every
   resource that happens to share a Year Group with someone is actually
   meant for them (e.g. internal admin notes vs teacher-facing content).

The staff member with is_primary_contact ticked (the school's own
Primary Contact) skips gates 2-3 entirely for their OWN school and sees
everything allocated to it - they're the one deciding what reaches who,
so they need full visibility, not the filtered view regular staff get.

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
RESOURCE_STAFF_DOCTYPE = "Knowledge Vault Resource Staff"

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


def get_knowledge_vault_resources_for_school_staff(organisation, role=None, year_group=None, membership=None, is_admin=False):
    """The one function school_dashboard actually calls (via a thin
    wrapper in its own api/school.py) - organisation/role/year_group/
    membership/is_admin are already-resolved values from the caller's
    own Organisation Membership lookup (ensure_organisation_access),
    never trusted from raw request input, since this has no login check
    of its own.

    is_admin=True (the school's own Primary Contact) returns every
    active resource allocated to this organisation, unfiltered - see
    this module's own docstring for why.

    Otherwise a resource matches when: it's active, this organisation is
    one of its allocated_schools, AND EITHER (its target_roles is empty
    OR role is in it) AND (its target_year_groups is empty OR year_group
    is in it) OR membership is explicitly in its staff_grants - the
    Role/Year Group side uses AND between the two dimensions
    deliberately (a resource targeted at both "Teaching Assistant" and
    "Year 2" is for a Year 2 TA specifically, not every TA or every Year
    2 staff member), while staff_grants is a flat OR on top of that -
    an explicit grant always gets someone in, regardless of their own
    Role/Year Group."""
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

    granted_resource_names = set()
    if not is_admin and membership:
        granted_resource_names = set(frappe.get_all(
            RESOURCE_STAFF_DOCTYPE,
            filters={"parent": ["in", list(resource_names)], "staff_member": membership},
            pluck="parent",
        ))

    results = []
    for row in docs:
        if not is_admin:
            roles = _parse_list(row.target_roles)
            year_groups = _parse_list(row.target_year_groups)
            auto_matches = (not roles or role in roles) and (not year_groups or year_group in year_groups)

            if not auto_matches and row.name not in granted_resource_names:
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


def get_resource_staff_grants_for_school(organisation):
    """Every resource allocated to `organisation`, with which of its own
    staff have been explicitly granted it - for the school admin's own
    allocation screen. Same no-login-check-of-its-own reasoning as
    get_knowledge_vault_resources_for_school_staff() - the caller has
    already confirmed the current user manages this organisation."""
    if not organisation:
        return []

    resource_names = [
        row.parent for row in
        frappe.get_all(RESOURCE_SCHOOL_DOCTYPE, filters={"school": organisation}, fields=["parent"])
    ]
    if not resource_names:
        return []

    docs = frappe.get_all(
        RESOURCE_DOCTYPE,
        filters={"name": ["in", resource_names], "is_active": 1},
        fields=["name", "title", "resource_type"],
        order_by="modified desc",
    )

    grants_by_resource = {}
    for row in frappe.get_all(RESOURCE_STAFF_DOCTYPE, filters={"parent": ["in", resource_names]}, fields=["parent", "staff_member"]):
        grants_by_resource.setdefault(row.parent, []).append(row.staff_member)

    return [
        {
            "name": doc.name,
            "title": doc.title,
            "resource_type": doc.resource_type or "",
            "granted_staff": grants_by_resource.get(doc.name, []),
        }
        for doc in docs
    ]


def set_resource_staff_grants(resource, organisation, staff_members):
    """Replaces the full staff_grants list for `resource` with
    `staff_members`. organisation/the caller's own permission to manage
    it are the caller's responsibility (same pattern as this module's
    other school-facing functions) - this only double-checks that
    `resource` is actually allocated to `organisation` (so a school
    admin can never grant access to a resource their own school was
    never given) and that every staff_member is a real, Active
    Organisation Membership row at that same organisation (so they can
    never grant it to someone at a different school)."""
    if not frappe.db.exists(RESOURCE_DOCTYPE, resource):
        frappe.throw(_("Resource not found."))

    if not frappe.db.exists(RESOURCE_SCHOOL_DOCTYPE, {"parent": resource, "school": organisation}):
        frappe.throw(_("This resource isn't allocated to your school."))

    valid_staff = set(frappe.get_all(
        "Organisation Membership",
        filters={"organisation": organisation, "membership_status": "Active"},
        pluck="name",
    ))

    if isinstance(staff_members, str):
        staff_members = frappe.parse_json(staff_members) if staff_members else []
    staff_members = [s for s in (staff_members or []) if s in valid_staff]

    doc = frappe.get_doc(RESOURCE_DOCTYPE, resource)
    doc.set("staff_grants", [])
    for staff_member in staff_members:
        doc.append("staff_grants", {"staff_member": staff_member})
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"ok": True}
