"""
Weight-based shipping for the online Store - a real product (not a
course, a digital download, or a service) has a weight; the Store
dashboard's own Shipping settings page turns a cart's total weight into
a flat fee, charged on a Store checkout and on a Coach Store order where
the coach has chosen "Shipping" over "Collection" - never on a course-
only or digital-only cart. See webshop_purchase.py's create_checkout_
session (public checkout, always charges it when the cart is physical)
and create_coach_store_order (Coach Store, only when delivery_method is
"Shipping") - the only two places this module's calculate_shipping_
amount() is actually called from.
"""

import frappe

from dashboard.api.shared.store_products import (
    _ensure_store_access,
    _as_administrator,
    _ensure_item_group,
    _ensure_item_default_row,
    _to_bool,
    _to_float,
)
from dashboard.dashboard.doctype.webshop_shipping_settings.webshop_shipping_settings import (
    get_shipping_settings,
)

# Deliberately not custom_store_enabled - stays out of the general store
# grid (get_store_items() filters on that flag) and off every other
# product listing, only ever added to a Webshop Checkout's own items
# programmatically (see _apply_shipping_to_checkout in webshop_purchase.py).
SHIPPING_ITEM_CODE = "SHIPPING-FEE"
SHIPPING_ITEM_GROUP = "Shipping"


def item_weight_grams(item_doc):
    """item_doc is anything dict-like with custom_weight/custom_weight_unit
    - an Item doc, or a plain dict from frappe.db.get_value(..., as_dict=True).
    Weight is stored exactly as a Store Manager typed it (see the field's
    own patch, add_item_weight_field.py) - this is the one place that
    converts it to grams for a shipping calculation."""
    weight = _to_float(item_doc.get("custom_weight"))
    unit = item_doc.get("custom_weight_unit") or "g"

    if str(unit).strip().lower() == "kg":
        return weight * 1000

    return weight


def is_shippable_item(item_doc):
    """False for anything that never needs posting, regardless of what
    weight (if any) is on it - a course-unlocking Item or a digital
    download, same two categories webshop_purchase.py already treats
    specially elsewhere. A "service" sold through the store has no
    dedicated flag of its own, but naturally never accrues shipping
    weight as long as its own Weight field is left at 0."""
    if item_doc.get("custom_unlocks_lms_course"):
        return False
    if item_doc.get("custom_digital_file"):
        return False
    return True


def _ensure_shipping_item(company):
    """Lazily creates the one synthetic Item a shipping charge is
    invoiced against - same pattern as store_products._ensure_course_item,
    just simpler (fixed name/price, no per-course sync needed)."""
    if frappe.db.exists("Item", SHIPPING_ITEM_CODE):
        return SHIPPING_ITEM_CODE

    item = frappe.new_doc("Item")
    item.item_code = SHIPPING_ITEM_CODE
    item.item_name = "Shipping"
    item.stock_uom = "Nos"
    item.is_stock_item = 0
    item.item_group = _ensure_item_group(SHIPPING_ITEM_GROUP)
    item.disabled = 0
    item.custom_store_enabled = 0

    _ensure_item_default_row(item, company)

    with _as_administrator():
        item.insert(ignore_permissions=True)

    frappe.db.commit()

    return SHIPPING_ITEM_CODE


def calculate_shipping_amount(total_weight_grams):
    """Flat fee for a cart whose shippable items together weigh
    total_weight_grams - the five Store-configured bands (see the
    Webshop Shipping Settings doctype), falling through to the
    "Over 5kg" rate for anything heavier so a big order never fails at
    checkout for having no matching band. Returns 0 if shipping is
    switched off, or the cart has no shippable weight at all (a
    course/digital/service-only cart, or every physical item still
    missing a Weight)."""
    if not total_weight_grams or total_weight_grams <= 0:
        return 0.0

    settings = get_shipping_settings()

    if not settings.shipping_enabled:
        return 0.0

    total_kg = total_weight_grams / 1000.0

    bands = [
        (1, settings.rate_under_1kg),
        (2, settings.rate_under_2kg),
        (3, settings.rate_under_3kg),
        (4, settings.rate_under_4kg),
        (5, settings.rate_under_5kg),
    ]

    for limit_kg, rate in bands:
        if total_kg <= limit_kg:
            return _to_float(rate)

    return _to_float(settings.rate_over_5kg)


@frappe.whitelist()
def get_shipping_settings_for_ui():
    _ensure_store_access()

    settings = get_shipping_settings()

    return {
        "shipping_enabled": bool(settings.shipping_enabled),
        "rate_under_1kg": settings.rate_under_1kg or 0,
        "rate_under_2kg": settings.rate_under_2kg or 0,
        "rate_under_3kg": settings.rate_under_3kg or 0,
        "rate_under_4kg": settings.rate_under_4kg or 0,
        "rate_under_5kg": settings.rate_under_5kg or 0,
        "rate_over_5kg": settings.rate_over_5kg or 0,
    }


@frappe.whitelist()
def save_shipping_settings(
    shipping_enabled=None,
    rate_under_1kg=None,
    rate_under_2kg=None,
    rate_under_3kg=None,
    rate_under_4kg=None,
    rate_under_5kg=None,
    rate_over_5kg=None,
):
    _ensure_store_access()

    settings = get_shipping_settings()
    settings.shipping_enabled = 1 if _to_bool(shipping_enabled) else 0
    settings.rate_under_1kg = _to_float(rate_under_1kg)
    settings.rate_under_2kg = _to_float(rate_under_2kg)
    settings.rate_under_3kg = _to_float(rate_under_3kg)
    settings.rate_under_4kg = _to_float(rate_under_4kg)
    settings.rate_under_5kg = _to_float(rate_under_5kg)
    settings.rate_over_5kg = _to_float(rate_over_5kg)
    settings.save(ignore_permissions=True)
    frappe.db.commit()

    return {"ok": 1}
