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

import re

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


def _parse_json_list(value):
    if not value:
        return []
    if isinstance(value, list):
        return value
    try:
        return frappe.parse_json(value) or []
    except Exception:
        return []


def _slugify(value):
    return "".join(ch if ch.isalnum() else "-" for ch in str(value).strip().lower()).strip("-")


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


def _root_item_group():
    root = frappe.db.get_value(
        "Item Group", {"is_group": 1, "parent_item_group": ["in", ["", None]]}, "name"
    )
    return root or "All Item Groups"


def _ensure_item_group(item_group_name):
    """
    The product form's own Item Group field is free text (with existing
    groups only offered as suggestions, per get_item_groups() below) -
    typing a brand new one (or even relying on the "Products" fallback,
    if that group was never actually created) used to fail outright with
    a LinkValidationError, since Item Group is a real Link field. Creates
    it on the fly instead, same on-demand pattern as
    email_groups.ensure_email_group().
    """
    item_group_name = (item_group_name or "").strip()

    if not item_group_name or frappe.db.exists("Item Group", item_group_name):
        return item_group_name

    doc = frappe.new_doc("Item Group")
    doc.item_group_name = item_group_name
    doc.parent_item_group = _root_item_group()
    doc.is_group = 0
    doc.insert(ignore_permissions=True)

    return doc.name


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
def get_lms_courses():
    """
    Every course, not just published ones - a Restricted or unpublished
    course is exactly the kind of thing meant to be granted by a specific
    purchase rather than open self-signup, so it still needs to show up
    here to be picked as what a product unlocks.
    """
    _ensure_store_access()

    if not frappe.db.exists("DocType", "LMS Course"):
        return []

    return frappe.get_all(
        "LMS Course",
        fields=["name", "title"],
        order_by="title asc",
        limit_page_length=500,
    )


def _unique_abbr(value, used_abbrs):
    """A naive value[:5] truncation collides constantly for values that
    share a common prefix (e.g. "Size 6-7" / "Size 7-8" both truncate to
    "SIZE "), which Item Attribute Value rejects as a duplicate
    abbreviation within the same attribute - build a real one instead:
    strip to alphanumerics, and disambiguate with a counter suffix on
    collision rather than ever reusing one already taken."""
    base = re.sub(r"[^A-Za-z0-9]+", "", value).upper()[:8] or "VAL"
    abbr = base
    counter = 1

    while abbr in used_abbrs:
        counter += 1
        abbr = f"{base}{counter}"

    used_abbrs.add(abbr)
    return abbr


def _ensure_item_attribute(attribute_name, values):
    """Creates the Item Attribute if missing, and adds any new values to
    it - existing values are never removed, since other items/variants
    may already depend on them."""
    attribute_name = (attribute_name or "").strip()

    if not attribute_name:
        return

    if frappe.db.exists("Item Attribute", attribute_name):
        doc = frappe.get_doc("Item Attribute", attribute_name)
    else:
        doc = frappe.new_doc("Item Attribute")
        doc.attribute_name = attribute_name

    existing_values = {row.attribute_value for row in doc.get("item_attribute_values") or []}
    value_meta_has_abbr = frappe.get_meta("Item Attribute Value").has_field("abbr") if frappe.db.exists("DocType", "Item Attribute Value") else False
    used_abbrs = {row.abbr for row in doc.get("item_attribute_values") or [] if row.get("abbr")}

    for value in values:
        value = (value or "").strip()
        if not value or value in existing_values:
            continue

        new_row = {"attribute_value": value}
        if value_meta_has_abbr:
            new_row["abbr"] = _unique_abbr(value, used_abbrs)

        doc.append("item_attribute_values", new_row)
        existing_values.add(value)

    if doc.is_new():
        doc.insert(ignore_permissions=True)
    else:
        doc.save(ignore_permissions=True)


@frappe.whitelist()
def get_store_products(search=None):
    _ensure_store_access()

    item_meta = frappe.get_meta("Item")
    brand_fieldnames = [f for f in BRAND_FIELDNAMES if item_meta.has_field(f)]

    filters = {"custom_store_enabled": 1}
    search = (search or "").strip()
    if search:
        filters["item_name"] = ["like", f"%{search}%"]

    extra_fieldnames = [
        f for f in ["custom_digital_file", "custom_unlocks_lms_course"] if item_meta.has_field(f)
    ]

    items = frappe.get_all(
        "Item",
        filters=filters,
        fields=(
            ["name", "item_name", "description", "item_group", "image", "disabled",
             "custom_stock_qty", "custom_unlimited_stock", "has_variants", "variant_of"]
            + brand_fieldnames + extra_fieldnames
        ),
        order_by="item_name asc",
        limit_page_length=1000,
    )

    # A variant (e.g. one specific size) has custom_store_enabled set the
    # same as its template, so it'd otherwise show up here as its own
    # separate row - only the template belongs in this list, its variants
    # are managed through get_product_variants() instead.
    items = [item for item in items if not item.variant_of]

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
            "digital_file": item.get("custom_digital_file") or "",
            "unlocks_course": item.get("custom_unlocks_lms_course") or "",
        }
        for item in items
    ]


@frappe.whitelist()
def create_store_product(item_name=None, description=None, item_group=None, price=None,
                          stock_qty=None, unlimited_stock=None, brands=None, image=None,
                          digital_file=None, unlocks_course=None):
    _ensure_store_access()

    item_name = (item_name or "").strip()

    if not item_name:
        frappe.throw(_("Product name is required."))

    company = _store_company()

    # An Item with this exact name can already exist without being a
    # store product yet - e.g. something tracked elsewhere in the system
    # (coaching stock, an old catalog entry) that Rachel now also wants
    # to sell online. Adopt it into the store rather than blocking with
    # a dead-end "already exists" error; only a name already used by
    # another *store* product is a genuine duplicate.
    existing_item_code = frappe.db.get_value("Item", {"item_name": item_name}, "name")
    is_new = not existing_item_code

    if existing_item_code:
        item = frappe.get_doc("Item", existing_item_code)

        if item.get("custom_store_enabled"):
            frappe.throw(_("A product named {0} already exists.").format(item_name))
    else:
        item = frappe.new_doc("Item")
        item.item_code = item_name
        item.item_name = item_name
        item.stock_uom = item.stock_uom or "Nos"
        item.is_stock_item = 0

    item.item_group = _ensure_item_group((item_group or "").strip() or item.item_group or "Products")
    item.description = description or item.description or ""
    item.disabled = 0
    item.custom_store_enabled = 1
    item.custom_unlimited_stock = 1 if _to_bool(unlimited_stock) else 0
    item.custom_stock_qty = _to_int(stock_qty)

    if image:
        item.image = image

    if digital_file and _item_meta_has_field("custom_digital_file"):
        item.custom_digital_file = digital_file

    if unlocks_course and _item_meta_has_field("custom_unlocks_lms_course"):
        item.custom_unlocks_lms_course = unlocks_course

    parsed_brands = _parse_brands(brands)
    for fieldname in BRAND_FIELDNAMES:
        if _item_meta_has_field(fieldname):
            item.set(fieldname, 1 if parsed_brands.get(fieldname) else 0)

    _ensure_item_default_row(item, company)

    if is_new:
        item.insert(ignore_permissions=True)
    else:
        item.save(ignore_permissions=True)

    if price is not None:
        _set_item_price(item.name, DEFAULT_PRICE_LIST, _to_float(price))

    frappe.db.commit()

    return {"ok": 1, "item_code": item.name}


@frappe.whitelist()
def update_store_product(item_code=None, item_name=None, description=None, item_group=None,
                          price=None, stock_qty=None, unlimited_stock=None, brands=None,
                          disabled=None, image=None, digital_file=None, unlocks_course=None):
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
        item.item_group = _ensure_item_group(item_group.strip())

    if stock_qty is not None:
        item.custom_stock_qty = _to_int(stock_qty)

    if unlimited_stock is not None:
        item.custom_unlimited_stock = 1 if _to_bool(unlimited_stock) else 0

    if disabled is not None:
        item.disabled = 1 if _to_bool(disabled) else 0

    if image is not None:
        item.image = image

    if digital_file is not None and _item_meta_has_field("custom_digital_file"):
        item.custom_digital_file = digital_file

    if unlocks_course is not None and _item_meta_has_field("custom_unlocks_lms_course"):
        item.custom_unlocks_lms_course = unlocks_course

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


# -------------------------------------------------------------------
# Variant products (e.g. a hoodie in several sizes/wordings, some sizes
# priced higher, each with its own stock count)
# -------------------------------------------------------------------

def _create_variant_item(template, attribute_values, price, stock_qty, unlimited_stock, company, image=None):
    suffix = "-".join(_slugify(v) for v in attribute_values.values()) or "VAR"
    item_code = f"{template.name}-{suffix}"

    variant = frappe.new_doc("Item")
    variant.item_code = item_code
    variant.item_name = template.item_name + " - " + " / ".join(attribute_values.values())
    variant.item_group = template.item_group
    variant.description = template.description
    variant.stock_uom = "Nos"
    variant.is_stock_item = 0
    variant.variant_of = template.name
    variant.custom_unlimited_stock = 1 if _to_bool(unlimited_stock) else 0
    variant.custom_stock_qty = _to_int(stock_qty)

    if image:
        variant.image = image
    elif template.image:
        variant.image = template.image

    for fieldname in BRAND_FIELDNAMES:
        if _item_meta_has_field(fieldname):
            variant.set(fieldname, template.get(fieldname))

    for attribute_name, value in attribute_values.items():
        variant.append("attributes", {"attribute": attribute_name, "attribute_value": value})

    _ensure_item_default_row(variant, company)

    variant.insert(ignore_permissions=True)

    price = _to_float(price)
    if price:
        _set_item_price(variant.name, DEFAULT_PRICE_LIST, price)

    return variant.name


@frappe.whitelist()
def create_variant_store_product(item_name=None, description=None, item_group=None,
                                  brands=None, image=None, attributes=None, variants=None):
    """
    attributes: [{"attribute": "Size", "values": ["Small", "Large"]}, ...]
    variants: [{"attribute_values": {"Size": "Small"}, "price": 10,
                "stock_qty": 5, "unlimited_stock": false}, ...]

    Creates the template Item (has_variants=1, never itself purchasable)
    plus one real Item per entry in `variants`, each with its own Item
    Default/Item Price/stock - exactly what webshop_purchase.py's
    get_item_or_variants() already knows how to read for checkout.
    """
    _ensure_store_access()

    item_name = (item_name or "").strip()

    if not item_name:
        frappe.throw(_("Product name is required."))

    if frappe.db.exists("Item", {"item_name": item_name}):
        # Unlike a plain product (create_store_product adopts a matching
        # non-store Item instead of blocking), turning an *existing* Item
        # into a variant template isn't safe to do automatically - it
        # already has its own price/stock history, and Frappe won't let
        # has_variants be switched on after that. A different name (or
        # renaming/removing the old Item first) is the only way forward.
        frappe.throw(_(
            "An item named {0} already exists and can't be converted into a product with "
            "variations. Choose a different name, or check the existing item in the Products list."
        ).format(item_name))

    attributes = _parse_json_list(attributes)
    variants = _parse_json_list(variants)

    if not attributes:
        frappe.throw(_("Add at least one attribute (e.g. Size) for a product with variations."))

    if not variants:
        frappe.throw(_("No variant combinations to create."))

    company = _store_company()

    for attr in attributes:
        _ensure_item_attribute(attr.get("attribute"), attr.get("values") or [])

    template = frappe.new_doc("Item")
    template.item_code = item_name
    template.item_name = item_name
    template.item_group = _ensure_item_group((item_group or "").strip() or "Products")
    template.description = description or ""
    template.stock_uom = "Nos"
    template.is_stock_item = 0
    template.has_variants = 1
    template.custom_store_enabled = 1

    if image:
        template.image = image

    parsed_brands = _parse_brands(brands)
    for fieldname in BRAND_FIELDNAMES:
        if _item_meta_has_field(fieldname):
            template.set(fieldname, 1 if parsed_brands.get(fieldname) else 0)

    for attr in attributes:
        template.append("attributes", {"attribute": attr.get("attribute")})

    template.insert(ignore_permissions=True)

    created = []
    first_variant_image = ""

    for variant_spec in variants:
        variant_image = (variant_spec.get("image") or "").strip()

        variant_name = _create_variant_item(
            template,
            variant_spec.get("attribute_values") or {},
            variant_spec.get("price"),
            variant_spec.get("stock_qty"),
            variant_spec.get("unlimited_stock"),
            company,
            image=variant_image,
        )
        created.append(variant_name)

        if variant_image and not first_variant_image:
            first_variant_image = variant_image

    # A variant template has no image of its own to show in a store
    # listing (get_store_items() only ever reads the template's image) -
    # fall back to whichever variant got one first, so the product still
    # has a thumbnail instead of the blank placeholder.
    if not template.image and first_variant_image:
        frappe.db.set_value("Item", template.name, "image", first_variant_image)

    frappe.db.commit()

    return {"ok": 1, "item_code": template.name, "variants": created}


@frappe.whitelist()
def get_product_variants(template_item_code=None):
    _ensure_store_access()

    template_item_code = (template_item_code or "").strip()

    variants = frappe.get_all(
        "Item",
        filters={"variant_of": template_item_code},
        fields=["name", "item_name", "image", "disabled", "custom_stock_qty", "custom_unlimited_stock"],
        order_by="item_name asc",
        limit_page_length=500,
    )

    result = []

    for variant in variants:
        attr_rows = frappe.get_all(
            "Item Variant Attribute",
            filters={"parent": variant.name, "parenttype": "Item"},
            fields=["attribute", "attribute_value"],
            order_by="idx asc",
        )
        price_row = _get_item_price_row(variant.name, DEFAULT_PRICE_LIST)

        result.append({
            "name": variant.name,
            "item_name": variant.item_name,
            "image": variant.image or "",
            "disabled": bool(variant.disabled),
            "stock_qty": variant.custom_stock_qty or 0,
            "unlimited_stock": bool(variant.custom_unlimited_stock),
            "price": price_row.price_list_rate if price_row else 0,
            "attributes": {row.attribute: row.attribute_value for row in attr_rows},
        })

    return result


@frappe.whitelist()
def update_variant(item_code=None, price=None, stock_qty=None, unlimited_stock=None, disabled=None, image=None):
    _ensure_store_access()

    item_code = (item_code or "").strip()

    if not item_code or not frappe.db.exists("Item", item_code):
        frappe.throw(_("Variant not found."))

    if stock_qty is not None:
        frappe.db.set_value("Item", item_code, "custom_stock_qty", _to_int(stock_qty))

    if unlimited_stock is not None:
        frappe.db.set_value("Item", item_code, "custom_unlimited_stock", 1 if _to_bool(unlimited_stock) else 0)

    if disabled is not None:
        frappe.db.set_value("Item", item_code, "disabled", 1 if _to_bool(disabled) else 0)

    if image:
        frappe.db.set_value("Item", item_code, "image", image)

        template_item_code = frappe.db.get_value("Item", item_code, "variant_of")
        if template_item_code and not frappe.db.get_value("Item", template_item_code, "image"):
            frappe.db.set_value("Item", template_item_code, "image", image)

    if price is not None:
        _set_item_price(item_code, DEFAULT_PRICE_LIST, _to_float(price))

    frappe.db.commit()

    return {"ok": 1}
