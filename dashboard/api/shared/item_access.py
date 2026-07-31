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
