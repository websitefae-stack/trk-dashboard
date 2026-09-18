"""
Store discount codes - "Store Coupon" is a simple percentage/fixed-amount
code a customer can enter at checkout, either store-wide or restricted
to specific products (and any of their variants). apply_coupon() is the
customer-facing preview call (cart page, before payment);
calculate_checkout_discount() is the same validation re-run server-side
inside create_checkout_session() itself, since a discount amount is
never trusted from the browser. The rest of this module is the Store
dashboard's own management of the list of codes (mirrors the create/
update/delete shape of store_products.py).
"""

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate

from dashboard.api.shared.store_products import _ensure_store_access, _parse_json_list

COUPON_DOCTYPE = "Store Coupon"
COUPON_ITEM_DOCTYPE = "Store Coupon Item"

SCOPE_ENTIRE_STORE = "Entire Store"
SCOPE_SPECIFIC_ITEMS = "Specific Items"

COUPON_LIST_FIELDS = [
    "name", "code", "discount_type", "discount_value", "active", "scope",
    "expiry_date", "max_uses", "times_used", "description",
]


def _normalize_code(code):
    return (code or "").strip().upper()


def _get_valid_coupon(code):
    """Loads a coupon by code and confirms it's actually usable right
    now - shared by the customer-facing preview and the real checkout
    calculation, so nothing can be honoured at checkout that would have
    been rejected at apply-time. Item eligibility is checked separately
    (see _eligible_subtotal) since that depends on what's actually in
    the cart, not just the code itself."""
    code = _normalize_code(code)

    if not code:
        frappe.throw(_("Please enter a discount code."))

    coupon_name = frappe.db.get_value(COUPON_DOCTYPE, {"code": code}, "name")

    if not coupon_name:
        frappe.throw(_("That discount code isn't valid."))

    coupon = frappe.get_doc(COUPON_DOCTYPE, coupon_name)

    if not coupon.active:
        frappe.throw(_("That discount code isn't valid."))

    if coupon.expiry_date and getdate(coupon.expiry_date) < getdate(nowdate()):
        frappe.throw(_("That discount code has expired."))

    if coupon.max_uses and coupon.times_used >= coupon.max_uses:
        frappe.throw(_("That discount code has already been fully redeemed."))

    return coupon


def _eligible_item_codes(coupon):
    """The exact set of item_codes a Specific-Items coupon counts towards -
    every item explicitly picked, plus every variant of any of them (a
    coupon set against a templated product like "Tote Bag" is meant to
    cover every colour/size of it, not just the bare template code,
    which is never itself sold directly)."""
    direct = {row.item for row in (coupon.items or []) if row.item}
    if not direct:
        return set()

    variant_codes = frappe.get_all(
        "Item", filters={"variant_of": ["in", list(direct)]}, pluck="name", ignore_permissions=True,
    )

    return direct | set(variant_codes)


def _eligible_subtotal(coupon, cart_items):
    """cart_items is [{item_code, qty, price}, ...]. A store-wide coupon
    counts the whole cart; a Specific-Items coupon only counts lines
    whose item_code (or its own template) was actually picked - anything
    else in the cart stays full price."""
    cart_items = cart_items or []

    if coupon.scope != SCOPE_SPECIFIC_ITEMS:
        return sum(flt(item.get("price")) * flt(item.get("qty") or 1) for item in cart_items)

    eligible_codes = _eligible_item_codes(coupon)
    if not eligible_codes:
        return 0

    return sum(
        flt(item.get("price")) * flt(item.get("qty") or 1)
        for item in cart_items
        if item.get("item_code") in eligible_codes
    )


def _discount_for(coupon, subtotal):
    subtotal = flt(subtotal)

    if coupon.discount_type == "Percentage":
        amount = subtotal * flt(coupon.discount_value) / 100
    else:
        amount = flt(coupon.discount_value)

    # Never below zero, and never more than whatever it's actually
    # discounting (the whole cart, or just the eligible items).
    return round(min(max(amount, 0), subtotal), 2)


@frappe.whitelist(allow_guest=True)
def apply_coupon(code=None, cart_items=None):
    coupon = _get_valid_coupon(code)
    cart_items = _parse_json_list(cart_items)
    eligible_subtotal = _eligible_subtotal(coupon, cart_items)

    if coupon.scope == SCOPE_SPECIFIC_ITEMS and eligible_subtotal <= 0:
        frappe.throw(_("This code isn't valid for anything in your cart."))

    discount_amount = _discount_for(coupon, eligible_subtotal)

    return {
        "code": coupon.code,
        "discount_type": coupon.discount_type,
        "discount_value": coupon.discount_value,
        "scope": coupon.scope,
        "eligible_item_codes": sorted(_eligible_item_codes(coupon)) if coupon.scope == SCOPE_SPECIFIC_ITEMS else [],
        "discount_amount": discount_amount,
    }


def calculate_checkout_discount(code, cart_items):
    """Used by create_checkout_session() itself - cart_items is
    [{item_code, qty, price}, ...] built from the same server-derived
    prices the checkout session itself charges, never anything sent by
    the browser. Returns (discount_amount, coupon_doc) rather than
    throwing, so an invalid/expired/no-longer-eligible code that somehow
    reaches here just applies no discount instead of blocking the whole
    checkout."""
    if not code:
        return 0, None

    try:
        coupon = _get_valid_coupon(code)
    except frappe.ValidationError:
        return 0, None

    eligible_subtotal = _eligible_subtotal(coupon, cart_items)
    if coupon.scope == SCOPE_SPECIFIC_ITEMS and eligible_subtotal <= 0:
        return 0, None

    return _discount_for(coupon, eligible_subtotal), coupon


def record_coupon_use(code):
    if not code:
        return

    frappe.db.sql(
        "UPDATE `tabStore Coupon` SET times_used = times_used + 1 WHERE code = %s",
        _normalize_code(code),
    )


# ---------------------------------------------------------------------
# Store dashboard management
# ---------------------------------------------------------------------

def _coupon_item_rows(coupon):
    if not coupon.items:
        return []

    item_names = {
        row.name: (row.item_name or row.name)
        for row in frappe.get_all(
            "Item", filters={"name": ["in", [row.item for row in coupon.items if row.item]]},
            fields=["name", "item_name"],
        )
    }

    return [
        {"item": row.item, "item_name": item_names.get(row.item, row.item)}
        for row in coupon.items
        if row.item
    ]


@frappe.whitelist()
def get_coupons():
    _ensure_store_access()

    rows = frappe.get_all(
        COUPON_DOCTYPE,
        fields=COUPON_LIST_FIELDS,
        order_by="creation desc",
    )

    item_counts = {}
    for row in frappe.get_all(
        COUPON_ITEM_DOCTYPE, filters={"parenttype": COUPON_DOCTYPE}, fields=["parent"],
    ):
        item_counts[row.parent] = item_counts.get(row.parent, 0) + 1

    for row in rows:
        row["item_count"] = item_counts.get(row.name, 0)

    return rows


@frappe.whitelist()
def get_coupon(name=None):
    _ensure_store_access()

    if not name or not frappe.db.exists(COUPON_DOCTYPE, name):
        frappe.throw(_("Coupon not found."))

    coupon = frappe.get_doc(COUPON_DOCTYPE, name)

    return {
        "name": coupon.name,
        "code": coupon.code,
        "discount_type": coupon.discount_type,
        "discount_value": coupon.discount_value,
        "active": bool(coupon.active),
        "scope": coupon.scope,
        "items": _coupon_item_rows(coupon),
        "expiry_date": str(coupon.expiry_date or ""),
        "max_uses": coupon.max_uses or 0,
        "times_used": coupon.times_used or 0,
        "description": coupon.description or "",
    }


def _apply_scope_and_items(coupon, scope, items):
    if scope is not None:
        coupon.scope = scope if scope in (SCOPE_ENTIRE_STORE, SCOPE_SPECIFIC_ITEMS) else SCOPE_ENTIRE_STORE

    if items is not None:
        item_codes = [code for code in _parse_json_list(items) if code]

        invalid = [code for code in item_codes if not frappe.db.exists("Item", code)]
        if invalid:
            frappe.throw(_("Unknown item: {0}").format(", ".join(invalid)))

        coupon.set("items", [])
        for code in item_codes:
            coupon.append("items", {"item": code})

    if coupon.scope == SCOPE_SPECIFIC_ITEMS and not coupon.items:
        frappe.throw(_("Choose at least one item this coupon applies to, or set it to Entire Store."))


@frappe.whitelist()
def create_coupon(code=None, discount_type=None, discount_value=None, active=1, scope=None, items=None, expiry_date=None, max_uses=0, description=None):
    _ensure_store_access()

    code = _normalize_code(code)
    if not code:
        frappe.throw(_("Please enter a code."))

    if frappe.db.exists(COUPON_DOCTYPE, {"code": code}):
        frappe.throw(_("A coupon with that code already exists."))

    if not flt(discount_value) > 0:
        frappe.throw(_("Please enter a discount value greater than zero."))

    coupon = frappe.new_doc(COUPON_DOCTYPE)
    coupon.code = code
    coupon.discount_type = discount_type or "Percentage"
    coupon.discount_value = flt(discount_value)
    coupon.active = cint(active)
    coupon.scope = SCOPE_ENTIRE_STORE
    coupon.expiry_date = expiry_date or None
    coupon.max_uses = cint(max_uses)
    coupon.description = description or ""
    _apply_scope_and_items(coupon, scope, items)
    coupon.insert(ignore_permissions=True)
    frappe.db.commit()

    return {"ok": 1, "name": coupon.name}


@frappe.whitelist()
def update_coupon(name=None, discount_type=None, discount_value=None, active=None, scope=None, items=None, expiry_date=None, max_uses=None, description=None):
    _ensure_store_access()

    if not name or not frappe.db.exists(COUPON_DOCTYPE, name):
        frappe.throw(_("Coupon not found."))

    coupon = frappe.get_doc(COUPON_DOCTYPE, name)

    if discount_type is not None:
        coupon.discount_type = discount_type
    if discount_value is not None:
        coupon.discount_value = flt(discount_value)
    if active is not None:
        coupon.active = cint(active)
    if expiry_date is not None:
        coupon.expiry_date = expiry_date or None
    if max_uses is not None:
        coupon.max_uses = cint(max_uses)
    if description is not None:
        coupon.description = description

    _apply_scope_and_items(coupon, scope, items)

    coupon.save(ignore_permissions=True)
    frappe.db.commit()

    return {"ok": 1}


@frappe.whitelist()
def delete_coupon(name=None):
    _ensure_store_access()

    if not name or not frappe.db.exists(COUPON_DOCTYPE, name):
        frappe.throw(_("Coupon not found."))

    frappe.delete_doc(COUPON_DOCTYPE, name, ignore_permissions=True)
    frappe.db.commit()

    return {"ok": 1}
