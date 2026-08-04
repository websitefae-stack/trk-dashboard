"""
Franchisor-only management of which coaches can offer which Items, and
which of those get shown as a service on the coach's public profile
page(s) (resilient_domains' trh/trk/trt/trp/trs coach-profile sites).

A coach can only add an Item to an invoice if their own company appears
in that Item's Item Defaults (Stock > Item > Defaults tab) - see
get_link_options("Item") in invoices.py, which filters on exactly that.
This module is the franchisor-side grid for ticking/unticking that
access per coach per item, instead of having to open each Item in the
desk UI and add a row by hand.

Ticking Access adds a real Item Default row (company, default_warehouse,
default_price_list) on that Item; unticking removes it outright. Once
removed, invoices.get_link_options("Item") will no longer offer that
item to that coach - access disappears the same way it would if the row
had been deleted directly from the Item - and because the whole row is
gone, Show on Site (custom_show_on_site, which only ever lives on that
same row) is cleared right along with it: a coach can never appear to
publicly offer a service they've lost invoicing access to.

Which site(s) a service is even relevant to at all (independent of any
particular coach) is tracked directly on the Item itself via five
Check fields (custom_brand_hub/kid/teen/people/school) - resilient_domains'
coach-profile pages only ever show a service when ALL of: the coach has
access, that access has Show on Site ticked, and the item's own flag for
that specific brand is ticked.
"""

import frappe
from frappe import _

from dashboard.api.shared.permissions import ensure_office_user

DEFAULT_PRICE_LIST = "Coach Pricelist"

# Login fields tried in order to resolve a Coach record's own sign-in
# identity - matches invoices.py's _get_current_coach()/_get_coach_company()
# convention, since not every site has all of these fields.
COACH_LOGIN_FIELDS = ["user", "user_id", "email", "coach_email"]

# fieldname -> label shown on the Item Access page, and the exact Check
# fieldnames added on Item by the add_item_show_on_site_and_brand_fields
# patch - resilient_domains' five brand coach-profile pages (trh/trk/trt/
# trp/trs) each read their own one of these directly off the Item.
BRAND_FIELDS = {
    "custom_brand_hub": "The Resilient Hub",
    "custom_brand_kid": "The Resilient Kid",
    "custom_brand_teen": "The Resilient Teen",
    "custom_brand_people": "The Resilient People",
    "custom_brand_school": "The Resilient School",
}


def _get_coach_login(coach_name):
    meta = frappe.get_meta("Coach")

    for fieldname in COACH_LOGIN_FIELDS:
        if meta.has_field(fieldname):
            value = frappe.db.get_value("Coach", coach_name, fieldname)
            if value:
                return value

    return ""


def _has_doctype(doctype):
    return bool(frappe.db.exists("DocType", doctype))


def _get_default_warehouse_for_company(company):
    return frappe.db.get_value(
        "Warehouse",
        {"company": company, "is_group": 0, "disabled": 0},
        "name",
        order_by="creation asc",
    ) or ""


@frappe.whitelist()
def get_item_access_grid():
    ensure_office_user()

    item_meta = frappe.get_meta("Item")
    brand_fieldnames = [fieldname for fieldname in BRAND_FIELDS if item_meta.has_field(fieldname)]

    items = frappe.get_all(
        "Item",
        fields=["name", "item_name", *brand_fieldnames],
        order_by="item_name asc, name asc",
        limit_page_length=5000,
    )

    coaches = frappe.get_all(
        "Coach",
        filters={"company": ["is", "set"]},
        fields=["name", "coach_name", "company"],
        order_by="coach_name asc, name asc",
        limit_page_length=5000,
    )

    coach_companies = sorted({coach.get("company") for coach in coaches if coach.get("company")})

    item_default_meta = frappe.get_meta("Item Default")
    has_show_on_site_field = item_default_meta.has_field("custom_show_on_site")

    grants = []
    if coach_companies:
        fields = ["parent", "company"]
        if has_show_on_site_field:
            fields.append("custom_show_on_site")

        rows = frappe.get_all(
            "Item Default",
            filters={"company": ["in", coach_companies]},
            fields=fields,
            limit_page_length=100000,
        )
        grants = [
            {
                "item": row.get("parent"),
                "company": row.get("company"),
                "show_on_site": int(row.get("custom_show_on_site") or 0) if has_show_on_site_field else 0,
            }
            for row in rows
        ]

    return {
        "items": [
            {
                "name": item.get("name"),
                "label": item.get("item_name") or item.get("name"),
                "brands": {
                    fieldname: int(item.get(fieldname) or 0)
                    for fieldname in brand_fieldnames
                },
            }
            for item in items
        ],
        "coaches": [
            {
                "name": coach.get("name"),
                "label": coach.get("coach_name") or coach.get("name"),
                "company": coach.get("company"),
            }
            for coach in coaches
        ],
        "grants": grants,
        "brand_fields": [
            {"fieldname": fieldname, "label": label}
            for fieldname, label in BRAND_FIELDS.items()
            if fieldname in brand_fieldnames
        ],
    }


@frappe.whitelist()
def set_item_access(item_code=None, coach=None, granted=None):
    ensure_office_user()

    item_code = (item_code or "").strip()
    coach = (coach or "").strip()
    granted = str(granted).strip().lower() in ("1", "true", "yes", "on")

    if not item_code or not frappe.db.exists("Item", item_code):
        frappe.throw(_("Item not found."))

    if not coach or not frappe.db.exists("Coach", coach):
        frappe.throw(_("Coach not found."))

    company = frappe.db.get_value("Coach", coach, "company")

    if not company:
        frappe.throw(_("This coach has no company set - please set one on their Coach record first."))

    item = frappe.get_doc("Item", item_code)

    existing_row = None
    for row in item.get("item_defaults") or []:
        if row.get("company") == company:
            existing_row = row
            break

    if granted:
        if existing_row:
            return {"ok": 1}

        warehouse = _get_default_warehouse_for_company(company)

        if not warehouse:
            frappe.throw(
                _("No default warehouse found for {0} - please set one up before granting access.").format(company)
            )

        item.append("item_defaults", {
            "company": company,
            "default_warehouse": warehouse,
            "default_price_list": DEFAULT_PRICE_LIST,
        })
        item.save(ignore_permissions=True)

    else:
        if not existing_row:
            return {"ok": 1}

        item.remove(existing_row)
        item.save(ignore_permissions=True)

    _resync_resource_access_for_item(item_code)
    frappe.db.commit()

    return {"ok": 1}


@frappe.whitelist()
def set_item_show_on_site(item_code=None, coach=None, show_on_site=None):
    ensure_office_user()

    item_code = (item_code or "").strip()
    coach = (coach or "").strip()
    show_on_site = str(show_on_site).strip().lower() in ("1", "true", "yes", "on")

    if not item_code or not frappe.db.exists("Item", item_code):
        frappe.throw(_("Item not found."))

    if not coach or not frappe.db.exists("Coach", coach):
        frappe.throw(_("Coach not found."))

    company = frappe.db.get_value("Coach", coach, "company")

    if not company:
        frappe.throw(_("This coach has no company set - please set one on their Coach record first."))

    item = frappe.get_doc("Item", item_code)

    existing_row = None
    for row in item.get("item_defaults") or []:
        if row.get("company") == company:
            existing_row = row
            break

    if not existing_row:
        frappe.throw(_("Grant this coach access to the item before showing it on their public profile."))

    existing_row.custom_show_on_site = 1 if show_on_site else 0
    item.save(ignore_permissions=True)
    frappe.db.commit()

    return {"ok": 1}


@frappe.whitelist()
def set_item_brand(item_code=None, brand_field=None, enabled=None):
    ensure_office_user()

    item_code = (item_code or "").strip()
    brand_field = (brand_field or "").strip()
    enabled = str(enabled).strip().lower() in ("1", "true", "yes", "on")

    if not item_code or not frappe.db.exists("Item", item_code):
        frappe.throw(_("Item not found."))

    if brand_field not in BRAND_FIELDS:
        frappe.throw(_("Unknown brand."))

    if not frappe.get_meta("Item").has_field(brand_field):
        frappe.throw(_("This site hasn't been migrated for brand visibility yet."))

    frappe.db.set_value("Item", item_code, brand_field, 1 if enabled else 0)
    frappe.db.commit()

    return {"ok": 1}


@frappe.whitelist()
def grant_item_access_to_all_coaches(item_code=None, show_on_site=None):
    """
    "Give access to all coaches" button next to an item - grants Access
    (and, unless told otherwise, Show on Site) to every coach on the grid
    in one call instead of clicking every cell in the row by hand. Skips
    a coach entirely if their Coach record has no company set, the same
    way a single set_item_access() call would - rather than failing the
    whole batch over one bad record.
    """
    ensure_office_user()

    item_code = (item_code or "").strip()
    show_on_site = show_on_site is None or str(show_on_site).strip().lower() in ("1", "true", "yes", "on")

    if not item_code or not frappe.db.exists("Item", item_code):
        frappe.throw(_("Item not found."))

    coach_names = frappe.get_all(
        "Coach",
        filters={"company": ["is", "set"]},
        pluck="name",
    )

    skipped = []

    for coach_name in coach_names:
        try:
            set_item_access(item_code=item_code, coach=coach_name, granted=1)
            if show_on_site:
                set_item_show_on_site(item_code=item_code, coach=coach_name, show_on_site=1)
        except Exception:
            skipped.append(coach_name)

    return {"ok": 1, "granted": len(coach_names) - len(skipped), "skipped": skipped}


# =====================================================
# WORKSHOP RESOURCES (Item <-> Practice Document)
# =====================================================
#
# A workshop Item can have one or more Practice Documents attached as
# resources (a Canva template, a handout, ...) - see Practice
# Document.linked_items. Whenever Item Access changes for a coach, every
# Practice Document linked to that item gets its own coach list ("Available
# to Coaches") reconciled to match: a coach keeps resource access as long
# as they have Item Access to at least one item that document is linked
# to, dropped the moment none of them do. Rows added by hand in the Desk
# (granted_via_item_access left unticked) are never touched by this - see
# Practice Document Coach's own field description.

PRACTICE_DOCUMENT_DOCTYPE = "Practice Document"
PRACTICE_DOCUMENT_ITEM_DOCTYPE = "Practice Document Item"
PRACTICE_DOCUMENT_COACH_DOCTYPE = "Practice Document Coach"


def _get_linked_item_codes(practice_document_name):
    if not _has_doctype(PRACTICE_DOCUMENT_ITEM_DOCTYPE):
        return []

    return frappe.get_all(
        PRACTICE_DOCUMENT_ITEM_DOCTYPE,
        filters={"parent": practice_document_name, "parenttype": PRACTICE_DOCUMENT_DOCTYPE},
        pluck="item",
    )


def _get_documents_linked_to_item(item_code):
    if not _has_doctype(PRACTICE_DOCUMENT_ITEM_DOCTYPE):
        return []

    return frappe.get_all(
        PRACTICE_DOCUMENT_ITEM_DOCTYPE,
        filters={"item": item_code, "parenttype": PRACTICE_DOCUMENT_DOCTYPE},
        pluck="parent",
        distinct=True,
    )


def _get_coach_names_with_access_to_items(item_codes):
    if not item_codes:
        return set()

    companies = set(frappe.get_all(
        "Item Default",
        filters={"parent": ["in", item_codes]},
        pluck="company",
    ))

    if not companies:
        return set()

    return set(frappe.get_all(
        "Coach",
        filters={"company": ["in", list(companies)]},
        pluck="name",
    ))


def _resync_practice_document_coaches(practice_document_name):
    """
    Reconciles one Practice Document's "Available to Coaches" list.

    Item Access is authoritative the moment this document has any Linked
    Items: access is decided SOLELY by Item Access to at least one of
    them - Brand-Based Access isn't consulted at all in that case, and
    even a manually-added row (a Desk override) is removed if the coach
    isn't currently item-entitled, since once an item is linked the
    whole point is that item access is the one gate that matters. A
    document with NO Linked Items falls back to Brand-Based Access as
    its only automatic mechanism, and there a manually-added row IS left
    alone, since nothing else is deciding access for that document.

    Deliberately works on the child rows directly (frappe.get_doc on the
    row's own doctype) rather than loading and saving the whole Practice
    Document, since this app doesn't own whatever Server Scripts are
    attached to that doctype in Desk and a full save could trigger them
    unexpectedly for what's meant to be a narrow, surgical sync.

    This is the one place Item Access and Brand Access are reconciled,
    so it's called from both the Item Access side (this module's own
    hook/API calls below) and the Brand Access side
    (practice_documents._resync_practice_document_brand_access) rather
    than each maintaining its own separate resync.
    """
    if not practice_document_name or not frappe.db.exists(PRACTICE_DOCUMENT_DOCTYPE, practice_document_name):
        return

    if not frappe.get_meta(PRACTICE_DOCUMENT_DOCTYPE).has_field("linked_items"):
        return

    linked_item_codes = _get_linked_item_codes(practice_document_name)

    # A document with any Linked Items has to actually be gated by them -
    # Resource Availability defaults to "All Coaches" (its field default,
    # applied whether the document was created here or straight in the
    # Frappe Desk), and forgetting to flip that separately would otherwise
    # leave it visible to every coach regardless of what's linked, which
    # is exactly the opposite of the point of linking it to specific
    # items in the first place. Only ever pushes towards "Selected
    # Coaches" - a document with no linked items keeps whatever Resource
    # Availability it already had.
    if linked_item_codes and frappe.get_meta(PRACTICE_DOCUMENT_DOCTYPE).has_field("resource_availability"):
        current_availability = frappe.db.get_value(PRACTICE_DOCUMENT_DOCTYPE, practice_document_name, "resource_availability")
        if current_availability != "Selected Coaches":
            # Raw SQL rather than frappe.db.set_value() - on this site's
            # Frappe version (16.14.0), that call was throwing a MySQL
            # "Truncated incorrect DECIMAL value" error from inside its own
            # query-builder plumbing for this exact single-field update,
            # for reasons that traced to Frappe core, not this app. A
            # plain parameterised UPDATE sidesteps whatever that is.
            frappe.db.sql(
                "UPDATE `tabPractice Document` SET resource_availability=%s WHERE name=%s",
                ("Selected Coaches", practice_document_name),
            )

    existing_rows = frappe.get_all(
        PRACTICE_DOCUMENT_COACH_DOCTYPE,
        filters={"parent": practice_document_name, "parenttype": PRACTICE_DOCUMENT_DOCTYPE},
        fields=["name", "coach", "granted_via_item_access", "granted_via_brand_access"],
    )

    covered_coach_names = set()

    if linked_item_codes:
        target_coach_names = _get_coach_names_with_access_to_items(linked_item_codes)
        item_target_coach_names = target_coach_names
        brand_target_coach_names = set()

        for row in existing_rows:
            coach_name = row.get("coach")
            if coach_name:
                covered_coach_names.add(coach_name)

            if coach_name not in target_coach_names:
                # No exception for a hand-added row here - Item Access is
                # the sole gate once an item is linked.
                frappe.db.delete(PRACTICE_DOCUMENT_COACH_DOCTYPE, {"name": row.get("name")})
                covered_coach_names.discard(coach_name)
                continue

            # Still item-entitled - keep the row, and make sure its flags
            # reflect the true (item-only) reason, in case it was
            # previously granted via brand before this item was linked.
            if not row.get("granted_via_item_access") or row.get("granted_via_brand_access"):
                frappe.db.set_value(
                    PRACTICE_DOCUMENT_COACH_DOCTYPE, row.get("name"),
                    {"granted_via_item_access": 1, "granted_via_brand_access": 0},
                    update_modified=False,
                )
    else:
        # No Linked Items - Brand-Based Access is the only automatic
        # mechanism. Local import - practice_documents.py already
        # imports from this module at load time, so importing it back at
        # module level here would be circular; by the time this function
        # actually runs, both modules are fully loaded.
        from dashboard.api.shared.practice_documents import _get_coach_names_with_brand_access, _get_practice_document_brand_values

        brand_doc = frappe.get_doc(PRACTICE_DOCUMENT_DOCTYPE, practice_document_name)
        target_coach_names = _get_coach_names_with_brand_access(_get_practice_document_brand_values(brand_doc))
        brand_target_coach_names = target_coach_names
        item_target_coach_names = set()

        for row in existing_rows:
            coach_name = row.get("coach")
            if coach_name:
                covered_coach_names.add(coach_name)

            if not row.get("granted_via_brand_access"):
                # Hand-added (or a leftover item-only flag with no items
                # currently linked) - nothing else is deciding access for
                # this document, so leave it alone.
                continue

            if coach_name not in target_coach_names:
                frappe.db.delete(PRACTICE_DOCUMENT_COACH_DOCTYPE, {"name": row.get("name")})
                covered_coach_names.discard(coach_name)

    missing_coach_names = target_coach_names - covered_coach_names

    if not missing_coach_names:
        return

    next_idx = frappe.db.count(
        PRACTICE_DOCUMENT_COACH_DOCTYPE,
        filters={"parent": practice_document_name, "parenttype": PRACTICE_DOCUMENT_DOCTYPE},
    )

    for coach_name in missing_coach_names:
        login = _get_coach_login(coach_name)
        if not login:
            continue

        next_idx += 1
        new_row = frappe.get_doc({
            "doctype": PRACTICE_DOCUMENT_COACH_DOCTYPE,
            "parent": practice_document_name,
            "parenttype": PRACTICE_DOCUMENT_DOCTYPE,
            "parentfield": "available_to_coaches",
            "idx": next_idx,
            "coach": coach_name,
            "user": login,
            "coach_name": frappe.db.get_value("Coach", coach_name, "coach_name") or coach_name,
            "can_share": 1,
            "granted_via_item_access": 1 if coach_name in item_target_coach_names else 0,
            "granted_via_brand_access": 1 if coach_name in brand_target_coach_names else 0,
        })
        new_row.insert(ignore_permissions=True)


def _resync_resource_access_for_item(item_code):
    for practice_document_name in _get_documents_linked_to_item(item_code):
        _resync_practice_document_coaches(practice_document_name)


def sync_practice_document_resource_access(doc, method=None):
    """
    Practice Document.on_update hook (see hooks.py's doc_events) - Linked
    Items is managed directly on the document in the Frappe Desk, so this
    is the only thing that keeps Resource Availability and the coach list
    in sync with it. Runs on every save regardless of whether Linked
    Items actually changed (there's no reliable "did this field change"
    signal available from a plain on_update hook, and resyncing is cheap
    and idempotent) - deliberately not skipped just because Linked Items
    is now empty, since clearing it out is exactly when any previously
    auto-granted coach rows need removing too.

    Wrapped so this can never block the save it's hooked onto - a
    document being saved successfully always matters more than this
    reconciliation happening to complete in the same request (a document
    still without its Selected Coaches list can be caught by anyone
    saving it again, or by re-running the resync patch, but a document
    that can't be saved at all is a much bigger problem). Specifically
    needed after a MySQL "Truncated incorrect DECIMAL value" error on
    this site's Frappe version (16.14.0) turned out to survive even
    switching the update to a plain parameterised SQL statement - so
    whatever's actually causing it sits deeper than anything this app's
    own code controls.
    """
    try:
        _resync_practice_document_coaches(doc.name)
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Practice Document Resource Resync Failed - {doc.name}")
