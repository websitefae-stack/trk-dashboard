"""
Franchisor-facing "Knowledge Vault" content admin - lets office/Ashley
build a library of training videos/PDFs/images/documents, decide which
School organisations get access to each one at all, and narrow each one
further to specific staff Roles and/or Year Groups within those schools.
A school's own Primary Contact (is_primary_contact - not just anyone
with can_manage_users, which an admin can grant a colleague without
making them the Primary Contact) can additionally override that Role/
Year Group targeting per staff member, either way - hand-picking someone
in who wouldn't otherwise see it (staff_grants) or excluding someone who
otherwise would (staff_exclusions) - see get_knowledge_vault_resources_
for_school_staff() and set_resource_staff_grants() below for the full
rule.

Gates a non-admin staff member must clear to see a resource (see
get_knowledge_vault_resources_for_school_staff() below, the one
function school_dashboard actually calls):

1. Their own Organisation Membership has can_access_knowledge_vault
   ticked (client_portal's existing master on/off switch - unchanged by
   this module, checked by the caller before it ever reaches here).
2. Their school is one of the resource's allocated_schools.
3. They're NOT explicitly listed in the resource's staff_exclusions for
   their own organisation - this always wins, regardless of 4 below.
4. EITHER their own Role/Year Group match the resource's target_roles/
   target_year_groups (each blank = no restriction on that dimension,
   both must match when both are set) OR they're explicitly listed in
   the resource's staff_grants for their own organisation - confirmed
   live: a school's admin needs to hand-pick specific people on top of
   (not instead of) the broad Role/Year Group rule, since not every
   resource that happens to share a Year Group with someone is actually
   meant for them (e.g. internal admin notes vs teacher-facing content).

The staff member with is_primary_contact ticked (the school's own
Primary Contact) skips gates 2-4 entirely for their OWN school and sees
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
RESOURCE_VIEW_DOCTYPE = "Knowledge Vault Resource View"

RESOURCE_TYPE_OPTIONS = [
    "Video", "PDF", "Image", "Document", "Email Template",
    "Teacher Emails", "Parent Emails", "Teacher Crib Sheet", "Tools",
    "Session Summary", "Instructions", "Other",
]

# Same lists school_dashboard's own school.py defines for the staff-invite
# Role/Year Group selects - duplicated rather than cross-imported, same
# light-coupling already used between these sibling apps elsewhere.
SCHOOL_ROLE_OPTIONS = [
    "Head", "Senior Leader", "Teacher", "Teaching Assistant",
    "SENCO", "Pastoral Staff", "School Administrator", "Ambassador", "Other",
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
    one of its allocated_schools, it's not in this staff member's own
    staff_exclusions (an explicit override that beats everything else
    below - see set_resource_staff_grants()'s own docstring for why this
    exists), AND EITHER (its target_roles is empty OR role is in it) AND
    (its target_year_groups is empty OR year_group is in it) OR
    membership is explicitly in its staff_grants - the Role/Year Group
    side uses AND between the two dimensions deliberately (a resource
    targeted at both "Teaching Assistant" and "Year 2" is for a Year 2
    TA specifically, not every TA or every Year 2 staff member), while
    staff_grants is a flat OR on top of that - an explicit grant always
    gets someone in, regardless of their own Role/Year Group."""
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

    # Autoincrement-named doctype - row.name below comes back as a JSON/
    # Python NUMBER (same quirk already hit once on the franchisor Edit
    # button, see knowledge_vault.js's own comment), while "parent" on a
    # child table row is always a plain string column. row.name in
    # granted_resource_names (a set built from "parent" strings) was
    # therefore silently NEVER true - confirmed live: an explicit grant
    # or exclusion never actually took effect here, regardless of what
    # was saved. str() both sides consistently to fix it for good.
    granted_resource_names = set()
    excluded_resource_names = set()
    if not is_admin and membership and frappe.db.table_exists(RESOURCE_STAFF_DOCTYPE):
        granted_resource_names = {str(name) for name in frappe.get_all(
            RESOURCE_STAFF_DOCTYPE,
            filters={"parent": ["in", list(resource_names)], "parentfield": "staff_grants", "staff_member": membership},
            pluck="parent",
        )}
        excluded_resource_names = {str(name) for name in frappe.get_all(
            RESOURCE_STAFF_DOCTYPE,
            filters={"parent": ["in", list(resource_names)], "parentfield": "staff_exclusions", "staff_member": membership},
            pluck="parent",
        )}

    results = []
    for row in docs:
        if not is_admin:
            if str(row.name) in excluded_resource_names:
                continue

            roles = _parse_list(row.target_roles)
            year_groups = _parse_list(row.target_year_groups)
            auto_matches = (not roles or role in roles) and (not year_groups or year_group in year_groups)

            if not auto_matches and str(row.name) not in granted_resource_names:
                continue

        results.append({
            "name": row.name,
            "title": row.title,
            "description": row.description or "",
            "resource_type": row.resource_type or "",
            "file": row.file or "",
            "video_url": row.video_url or "",
            "text_content": row.get("text_content") or "",
            # Not used for the match logic above (already applied) - just
            # along for the ride so school_dashboard can sort its own
            # resource list by Year Group without a second round trip.
            "target_year_groups": _parse_list(row.target_year_groups),
        })

    return results


def _ensure_staff_grants_field_exists():
    """staff_grants/staff_exclusions are Table fields added by patches
    (add_staff_grants_to_knowledge_vault_resource.py,
    add_staff_exclusions_to_knowledge_vault_resource.py), not part of
    this doctype's original definition - if either patch hasn't actually
    run on this site yet (or failed partway, e.g. during one of this
    project's earlier deploy failures), frappe.get_doc(...).save()
    silently drops anything written to that field (not in the doctype's
    own meta, so get_valid_dict() filters it out before the INSERT/
    UPDATE), and a raw frappe.get_all(RESOURCE_STAFF_DOCTYPE, ...) throws
    a bare "table doesn't exist" SQL error instead of a clean message -
    either way, "Manage access" looked broken with no indication why.
    This turns that into one clear, actionable error instead."""
    meta = frappe.get_meta(RESOURCE_DOCTYPE)
    if not meta.has_field("staff_grants") or not meta.has_field("staff_exclusions") or not frappe.db.table_exists(RESOURCE_STAFF_DOCTYPE):
        frappe.throw(_(
            "Per-staff resource access isn't finished setting up on this site yet "
            "(Staff Grants/Staff Exclusions is missing) - this needs a fresh "
            "deploy/migrate to finish creating it before access can be hand-picked "
            "per staff member."
        ))


def get_resource_staff_grants_for_school(organisation):
    """Every resource allocated to `organisation`, with its own
    effective_staff - every one of the school's Active staff who
    currently actually sees it, combining Role/Year Group targeting,
    staff_grants and staff_exclusions exactly the way get_knowledge_
    vault_resources_for_school_staff() does for a single staff member -
    for the "Manage Access" screen's single tick-per-person checkbox,
    which is meant to be the final word either way (see
    set_resource_staff_grants()'s own docstring).

    Same no-login-check-of-its-own reasoning as get_knowledge_vault_
    resources_for_school_staff() - the caller has already confirmed the
    current user manages this organisation."""
    if not organisation:
        return []

    _ensure_staff_grants_field_exists()

    resource_names = [
        row.parent for row in
        frappe.get_all(RESOURCE_SCHOOL_DOCTYPE, filters={"school": organisation}, fields=["parent"])
    ]
    if not resource_names:
        return []

    docs = frappe.get_all(
        RESOURCE_DOCTYPE,
        filters={"name": ["in", resource_names], "is_active": 1},
        fields=["name", "title", "resource_type", "target_roles", "target_year_groups"],
        order_by="modified desc",
    )

    grants_by_resource = {}
    exclusions_by_resource = {}
    for row in frappe.get_all(RESOURCE_STAFF_DOCTYPE, filters={"parent": ["in", resource_names]}, fields=["parent", "parentfield", "staff_member"]):
        bucket = grants_by_resource if row.parentfield == "staff_grants" else exclusions_by_resource
        bucket.setdefault(str(row.parent), []).append(row.staff_member)

    staff_rows = frappe.get_all(
        "Organisation Membership",
        filters={"organisation": organisation, "membership_status": "Active"},
        fields=["name", "role", "year_group"],
    )

    results = []
    for doc in docs:
        roles = _parse_list(doc.target_roles)
        year_groups = _parse_list(doc.target_year_groups)
        # Autoincrement-named doctype - doc.name here is a Python number,
        # while the dicts above are keyed by the child row's own "parent"
        # string column (see this function's sibling, get_knowledge_
        # vault_resources_for_school_staff, for the fuller explanation of
        # this exact quirk). str() to actually match.
        granted = set(grants_by_resource.get(str(doc.name), []))
        excluded = set(exclusions_by_resource.get(str(doc.name), []))

        effective_staff = [
            staff.name for staff in staff_rows
            if staff.name not in excluded
            and (granted.__contains__(staff.name) or ((not roles or staff.role in roles) and (not year_groups or staff.year_group in year_groups)))
        ]

        results.append({
            "name": doc.name,
            "title": doc.title,
            "resource_type": doc.resource_type or "",
            "effective_staff": effective_staff,
        })

    return results


def set_resource_staff_grants(resource, organisation, staff_members):
    """Replaces WHO (among this school's own Active staff) can see
    `resource`, taking `staff_members` as the final, complete list of
    everyone who should have access - the Manage Access screen's one
    checkbox per person, ticked or not, is meant to settle it either
    way, overriding Role/Year Group targeting in both directions.
    Confirmed live: the old version only ever ADDED explicit grants on
    top of Role/Year Group targeting, so unticking someone who already
    had access through targeting was a silent no-op - it looked like
    "doesn't save" when really there was just no way to override an
    automatic match at all.

    Diffs `staff_members` against each Active staff member's own Role/
    Year Group auto-match for this resource: wanted-but-not-auto-
    matching goes in staff_grants (an explicit top-up, as before),
    auto-matching-but-not-wanted goes in the new staff_exclusions (an
    explicit override), and anyone who needs neither (because being in
    staff_members already agrees with their own auto-match, or they're
    not in staff_members and don't auto-match either) is removed from
    both.

    organisation/the caller's own permission to manage it are the
    caller's responsibility (same pattern as this module's other
    school-facing functions) - this only double-checks that `resource`
    is actually allocated to `organisation` (so a school admin can
    never grant access to a resource their own school was never given)
    and that every staff_member is a real, Active Organisation
    Membership row at that same organisation (so they can never grant
    it to, or exclude, someone at a different school)."""
    _ensure_staff_grants_field_exists()

    if not frappe.db.exists(RESOURCE_DOCTYPE, resource):
        frappe.throw(_("Resource not found."))

    if not frappe.db.exists(RESOURCE_SCHOOL_DOCTYPE, {"parent": resource, "school": organisation}):
        frappe.throw(_("This resource isn't allocated to your school."))

    staff_rows = frappe.get_all(
        "Organisation Membership",
        filters={"organisation": organisation, "membership_status": "Active"},
        fields=["name", "role", "year_group"],
    )

    if isinstance(staff_members, str):
        staff_members = frappe.parse_json(staff_members) if staff_members else []
    desired = set(staff_members or [])

    doc = frappe.get_doc(RESOURCE_DOCTYPE, resource)
    roles = _parse_list(doc.target_roles)
    year_groups = _parse_list(doc.target_year_groups)

    grants = []
    exclusions = []
    for staff in staff_rows:
        wants_access = staff.name in desired
        auto_matches = (not roles or staff.role in roles) and (not year_groups or staff.year_group in year_groups)

        if wants_access and not auto_matches:
            grants.append(staff.name)
        elif not wants_access and auto_matches:
            exclusions.append(staff.name)

    doc.set("staff_grants", [])
    for staff_member in grants:
        doc.append("staff_grants", {"staff_member": staff_member})

    doc.set("staff_exclusions", [])
    for staff_member in exclusions:
        doc.append("staff_exclusions", {"staff_member": staff_member})

    doc.save(ignore_permissions=True)
    frappe.db.commit()

    # Belt-and-braces: confirmed live that unticking someone looked like
    # it saved (no error) but came back unchanged on reopening - rather
    # than leave that as a silent, confusing no-op again, read the row
    # straight back from the DB (not the in-memory doc) and throw a
    # specific, actionable error the moment what's actually stored
    # doesn't match what was just asked for, instead of claiming success.
    saved_grants = set(frappe.get_all(
        RESOURCE_STAFF_DOCTYPE,
        filters={"parent": resource, "parentfield": "staff_grants"},
        pluck="staff_member",
    ))
    saved_exclusions = set(frappe.get_all(
        RESOURCE_STAFF_DOCTYPE,
        filters={"parent": resource, "parentfield": "staff_exclusions"},
        pluck="staff_member",
    ))

    if saved_grants != set(grants) or saved_exclusions != set(exclusions):
        frappe.throw(_(
            "This looked like it saved, but reading it straight back shows it didn't "
            "actually stick - that points to a setup problem with Staff Grants/Staff "
            "Exclusions on this site rather than anything wrong with what you picked. "
            "Please report this back rather than retrying."
        ))

    return {"ok": True}


# =====================================================
# RESOURCE VIEWS (watch tracking)
# =====================================================

def _resource_view_doctype_ready():
    return frappe.db.exists("DocType", RESOURCE_VIEW_DOCTYPE) and frappe.db.table_exists(RESOURCE_VIEW_DOCTYPE)


def record_resource_view(resource, organisation, membership):
    """Called via school_dashboard's own record_resource_view wrapper,
    the moment a staff member opens a resource's video/file link (not on
    later page loads of the resource list) - organisation/membership are
    already-resolved values from the caller's own Organisation
    Membership lookup, same trust model as get_knowledge_vault_
    resources_for_school_staff above - this has no login check of its
    own. Best-effort: never allowed to break opening the resource itself
    over a tracking write failing.

    Idempotent - only ever one row per (resource, membership), so
    re-opening the same video doesn't inflate anything; this tracks
    "did they ever watch it", not a play count."""
    if not resource or not organisation or not membership:
        return

    if not _resource_view_doctype_ready():
        return

    try:
        resource = str(resource)

        if frappe.db.exists(RESOURCE_VIEW_DOCTYPE, {"resource": resource, "membership": membership}):
            return

        doc = frappe.new_doc(RESOURCE_VIEW_DOCTYPE)
        doc.resource = resource
        doc.organisation = organisation
        doc.membership = membership
        doc.viewed_at = frappe.utils.now_datetime()
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Knowledge Vault Resource View Recording Failed")


def _staff_display_names(membership_names):
    if not membership_names:
        return {}

    rows = frappe.get_all(
        "Organisation Membership",
        filters={"name": ["in", list(membership_names)]},
        fields=["name", "user", "email"],
    )

    user_emails = {row.name: row.user for row in rows if row.user}
    full_names = {}
    if user_emails:
        for row in frappe.get_all("User", filters={"name": ["in", list(set(user_emails.values()))]}, fields=["name", "full_name"]):
            full_names[row.name] = row.full_name or row.name

    return {
        row.name: (full_names.get(row.user) if row.user else None) or row.email or row.name
        for row in rows
    }


def get_resource_watch_stats_for_school(organisation):
    """Primary-Contact-only (caller's job to gate, same pattern as this
    module's other school-facing functions) - for every resource
    allocated to `organisation`, how many of its own effective_staff
    (see get_resource_staff_grants_for_school) have actually watched it,
    and who has/hasn't - the school-side half of "which topics are our
    staff actually engaging with"."""
    grants = get_resource_staff_grants_for_school(organisation)
    if not grants:
        return []

    resource_names = [str(row["name"]) for row in grants]
    all_membership_names = {m for row in grants for m in row["effective_staff"]}

    watched_by_resource = {}
    if all_membership_names and _resource_view_doctype_ready():
        for row in frappe.get_all(
            RESOURCE_VIEW_DOCTYPE,
            filters={"resource": ["in", resource_names], "membership": ["in", list(all_membership_names)]},
            fields=["resource", "membership"],
        ):
            watched_by_resource.setdefault(row.resource, set()).add(row.membership)

    names_by_membership = _staff_display_names(all_membership_names)

    results = []
    for row in grants:
        effective = row["effective_staff"]
        watched = watched_by_resource.get(str(row["name"]), set())

        results.append({
            "name": row["name"],
            "title": row["title"],
            "resource_type": row["resource_type"],
            "staff_with_access": len(effective),
            "staff_watched": len(watched & set(effective)),
            "watched_names": sorted(names_by_membership.get(m, m) for m in watched if m in effective),
            "not_watched_names": sorted(names_by_membership.get(m, m) for m in effective if m not in watched),
        })

    return results


@frappe.whitelist()
def get_knowledge_vault_watch_report():
    """Franchisor-only - every Video resource ranked by how much of its
    own effective audience has actually watched it, both as an overall
    total across every school it's allocated to AND broken down per
    school, so a high overall number that's really just one school
    doesn't get mistaken for a widespread pattern. This is the "which
    topics are schools actually engaging with, and which specific school
    should we proactively reach out to" view - e.g. most of one school's
    staff watching the anxiety video is a workshop opportunity, not just
    a vanity metric."""
    _ensure_franchisor()

    resource_names = frappe.get_all(
        RESOURCE_DOCTYPE,
        filters={"resource_type": "Video", "is_active": 1},
        fields=["name", "title"],
        order_by="modified desc",
    )
    if not resource_names:
        return []

    school_rows = frappe.get_all(
        RESOURCE_SCHOOL_DOCTYPE,
        filters={"parent": ["in", [str(r.name) for r in resource_names]]},
        fields=["parent", "school"],
    )
    schools_by_resource = {}
    for row in school_rows:
        schools_by_resource.setdefault(str(row.parent), []).append(row.school)

    school_names = {
        row.name: (row.customer_name or row.name)
        for row in frappe.get_all(
            "Customer",
            filters={"name": ["in", list({s for schools in schools_by_resource.values() for s in schools})]},
            fields=["name", "customer_name"],
        )
    } if schools_by_resource else {}

    results = []
    for resource in resource_names:
        resource_name = str(resource.name)
        schools = schools_by_resource.get(resource_name, [])

        total_access = 0
        total_watched = 0
        per_school = []

        for school in schools:
            school_stats = get_resource_watch_stats_for_school(school)
            match = next((row for row in school_stats if str(row["name"]) == resource_name), None)
            if not match:
                continue

            total_access += match["staff_with_access"]
            total_watched += match["staff_watched"]
            per_school.append({
                "school": school,
                "school_label": school_names.get(school, school),
                "staff_with_access": match["staff_with_access"],
                "staff_watched": match["staff_watched"],
            })

        per_school.sort(key=lambda row: row["staff_watched"], reverse=True)

        results.append({
            "name": resource.name,
            "title": resource.title,
            "staff_with_access": total_access,
            "staff_watched": total_watched,
            "watch_rate": round(100 * total_watched / total_access, 1) if total_access else 0,
            "schools": per_school,
        })

    results.sort(key=lambda row: row["staff_watched"], reverse=True)
    return results
