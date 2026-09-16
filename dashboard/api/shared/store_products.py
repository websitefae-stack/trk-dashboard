"""
Store Manager's own product/stock management (see permissions.py's
Store Manager dashboard type) - a franchisor can also use every
endpoint here, but a Store Manager can't reach anything outside it.

Deliberately separate from item_access.py, which stays exactly what it
already was: the franchisor-only grid for granting individual coaches
invoicing access to an Item. A store product still needs the same
underlying Item Default (company/warehouse/price list) + Item Price
rows webshop_purchase.py's checkout already reads prices from, so
those two pieces are reused directly rather than re-implemented here.
"""

import frappe
from frappe import _

from dashboard.api.shared.permissions import ensure_logged_in, is_office_user, is_store_manager
from dashboard.api.shared.item_access import DEFAULT_PRICE_LIST, BRAND_FIELDS, _get_default_warehouse_for_company
from dashboard.dashboard.doctype.webshop_payment_settings.webshop_payment_settings import get_settings

BRAND_FIELDNAMES = list(BRAND_FIELDS.keys())


def _ensure_store_access():
    ensure_logged_in()

    if not (is_office_user() or is_store_manager()):
        frappe.throw(_("You are not allowed to manage the store."), frappe.PermissionError)


def _to_bool(value):
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _to_int(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _to_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _item_meta_has_field(fieldname):
    return frappe.get_meta("Item").has_field(fieldname)


def _parse_brands(brands):
    if not brands:
        return {}
    if isinstance(brands, dict):
        return brands
    try:
        return frappe.parse_json(brands) or {}
    except Exception:
        return {}


def _store_company():
    settings = get_settings()

    if not settings.company:
        frappe.throw(_("Set a Company on Webshop Payment Settings before managing store products."))

    return settings.company


def _ensure_item_default_row(item, company):
    for row in item.get("item_defaults") or []:
        if row.get("company") == company:
            return row

    warehouse = _get_default_warehouse_for_company(company)

    if not warehouse:
        frappe.throw(_("No default warehouse found for {0} - please set one up first.").format(company))

    item.append("item_defaults", {
        "company": company,
        "default_warehouse": warehouse,
        "default_price_list": DEFAULT_PRICE_LIST,
    })

    return item.get("item_defaults")[-1]


def _get_item_price_row(item_code, price_list):
    return frappe.db.get_value(
        "Item Price",
        {"item_code": item_code, "price_list": price_list, "selling": 1},
        ["name", "price_list_rate"],
        as_dict=True,
    )


def _set_item_price(item_code, price_list, rate):
    existing = _get_item_price_row(item_code, price_list)

    if existing:
        frappe.db.set_value("Item Price", existing.name, "price_list_rate", rate)
        return existing.name

    price_doc = frappe.new_doc("Item Price")
    price_doc.item_code = item_code
    price_doc.price_list = price_list
    price_doc.selling = 1
    price_doc.price_list_rate = rate
    price_doc.currency = "GBP"
    price_doc.insert(ignore_permissions=True)

    return price_doc.name


@frappe.whitelist()
def get_item_groups():
    _ensure_store_access()

    return frappe.get_all(
        "Item Group",
        filters={"is_group": 0},
        pluck="name",
        order_by="name asc",
        limit_page_length=200,
    )


@frappe.whitelist()
def get_store_products(search=None):
    _ensure_store_access()

    item_meta = frappe.get_meta("Item")
    brand_fieldnames = [f for f in BRAND_FIELDNAMES if item_meta.has_field(f)]

    filters = {"custom_store_enabled": 1}
    search = (search or "").strip()
    if search:
        filters["item_name"] = ["like", f"%{search}%"]

    items = frappe.get_all(
        "Item",
        filters=filters,
        fields=(
            ["name", "item_name", "description", "item_group", "image", "disabled",
             "custom_stock_qty", "custom_unlimited_stock", "has_variants"]
            + brand_fieldnames
        ),
        order_by="item_name asc",
        limit_page_length=1000,
    )

    prices = {}
    if items:
        price_rows = frappe.get_all(
            "Item Price",
            filters={
                "price_list": DEFAULT_PRICE_LIST,
                "selling": 1,
                "item_code": ["in", [i.name for i in items]],
            },
            fields=["item_code", "price_list_rate"],
        )
        prices = {row.item_code: row.price_list_rate for row in price_rows}

    return [
        {
            "name": item.name,
            "item_name": item.item_name or item.name,
            "description": item.description or "",
            "item_group": item.item_group or "",
            "image": item.image or "",
            "disabled": bool(item.disabled),
            "has_variants": bool(item.has_variants),
            "stock_qty": item.custom_stock_qty or 0,
            "unlimited_stock": bool(item.custom_unlimited_stock),
            "price": prices.get(item.name) or 0,
            "brands": {fieldname: bool(item.get(fieldname)) for fieldname in brand_fieldnames},
        }
        for item in items
    ]


@frappe.whitelist()
def create_store_product(item_name=None, description=None, item_group=None, price=None,
                          stock_qty=None, unlimited_stock=None, brands=None, image=None):
    _ensure_store_access()

    item_name = (item_name or "").strip()

    if not item_name:
        frappe.throw(_("Product name is required."))

    if frappe.db.exists("Item", {"item_name": item_name}):
        frappe.throw(_("A product named {0} already exists.").format(item_name))

    company = _store_company()

    item = frappe.new_doc("Item")
    item.item_code = item_name
    item.item_name = item_name
    item.item_group = (item_group or "").strip() or "Products"
    item.description = description or ""
    item.stock_uom = "Nos"
    item.is_stock_item = 0
    item.disabled = 0
    item.custom_store_enabled = 1
    item.custom_unlimited_stock = 1 if _to_bool(unlimited_stock) else 0
    item.custom_stock_qty = _to_int(stock_qty)

    if image:
        item.image = image

    parsed_brands = _parse_brands(brands)
    for fieldname in BRAND_FIELDNAMES:
        if _item_meta_has_field(fieldname):
            item.set(fieldname, 1 if parsed_brands.get(fieldname) else 0)

    _ensure_item_default_row(item, company)

    item.insert(ignore_permissions=True)

    if price is not None:
        _set_item_price(item.name, DEFAULT_PRICE_LIST, _to_float(price))

    frappe.db.commit()

    return {"ok": 1, "item_code": item.name}


@frappe.whitelist()
def update_store_product(item_code=None, item_name=None, description=None, item_group=None,
                          price=None, stock_qty=None, unlimited_stock=None, brands=None,
                          disabled=None, image=None):
    _ensure_store_access()

    item_code = (item_code or "").strip()

    if not item_code or not frappe.db.exists("Item", item_code):
        frappe.throw(_("Product not found."))

    item = frappe.get_doc("Item", item_code)

    if item_name is not None and item_name.strip():
        item.item_name = item_name.strip()

    if description is not None:
        item.description = description

    if item_group is not None and item_group.strip():
        item.item_group = item_group.strip()

    if stock_qty is not None:
        item.custom_stock_qty = _to_int(stock_qty)

    if unlimited_stock is not None:
        item.custom_unlimited_stock = 1 if _to_bool(unlimited_stock) else 0

    if disabled is not None:
        item.disabled = 1 if _to_bool(disabled) else 0

    if image is not None:
        item.image = image

    parsed_brands = _parse_brands(brands)
    for fieldname in BRAND_FIELDNAMES:
        if fieldname in parsed_brands and _item_meta_has_field(fieldname):
            item.set(fieldname, 1 if parsed_brands.get(fieldname) else 0)

    company = _store_company()
    _ensure_item_default_row(item, company)

    item.save(ignore_permissions=True)

    if price is not None:
        _set_item_price(item.name, DEFAULT_PRICE_LIST, _to_float(price))

    frappe.db.commit()

    return {"ok": 1}


@frappe.whitelist()
def update_store_stock(item_code=None, stock_qty=None, unlimited_stock=None):
    """Fast path for just adjusting stock, without re-saving the whole Item."""
    _ensure_store_access()

    item_code = (item_code or "").strip()

    if not item_code or not frappe.db.exists("Item", item_code):
        frappe.throw(_("Product not found."))

    if unlimited_stock is not None:
        frappe.db.set_value("Item", item_code, "custom_unlimited_stock", 1 if _to_bool(unlimited_stock) else 0)

    if stock_qty is not None:
        frappe.db.set_value("Item", item_code, "custom_stock_qty", _to_int(stock_qty))

    frappe.db.commit()

    return {"ok": 1}
