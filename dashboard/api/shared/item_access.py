"""
Franchisor-only management of which coaches can offer which Items.

A coach can only add an Item to an invoice if their own company appears
in that Item's Item Defaults (Stock > Item > Defaults tab) - see
get_link_options("Item") in invoices.py, which filters on exactly that.
This module is the franchisor-side grid for ticking/unticking that
access per coach per item, instead of having to open each Item in the
desk UI and add a row by hand.

Ticking a box adds a real Item Default row (company, default_warehouse,
default_price_list) on that Item; unticking removes it outright. Once
removed, invoices.get_link_options("Item") will no longer offer that
item to that coach - access disappears the same way it would if the row
had been deleted directly from the Item.
"""

import frappe
from frappe import _

from dashboard.api.shared.permissions import ensure_office_user

DEFAULT_PRICE_LIST = "Coach Pricelist"


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

    items = frappe.get_all(
        "Item",
        fields=["name", "item_name"],
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

    grants = []
    if coach_companies:
        rows = frappe.get_all(
            "Item Default",
            filters={"company": ["in", coach_companies]},
            fields=["parent", "company"],
            limit_page_length=100000,
        )
        grants = [{"item": row.get("parent"), "company": row.get("company")} for row in rows]

    return {
        "items": [
            {"name": item.get("name"), "label": item.get("item_name") or item.get("name")}
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
