"""
Store discount codes - "Store Coupon" is a simple percentage/fixed-amount
code a customer can enter at checkout. apply_coupon() is the customer-
facing preview call (cart page, before payment); calculate_checkout_discount()
is the same validation re-run server-side inside create_checkout_session()
itself, since a discount amount is never trusted from the browser. The
rest of this module is the Store dashboard's own management of the list
of codes (mirrors the create/update/delete shape of store_products.py).
"""

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate

from dashboard.api.shared.store_products import _ensure_store_access

COUPON_DOCTYPE = "Store Coupon"

COUPON_LIST_FIELDS = [
    "name", "code", "discount_type", "discount_value", "active",
    "expiry_date", "max_uses", "times_used", "description",
]


def _normalize_code(code):
    return (code or "").strip().upper()


def _get_valid_coupon(code):
    """Loads a coupon by code and confirms it's actually usable right
    now - shared by the customer-facing preview and the real checkout
    calculation, so nothing can be honoured at checkout that would have
    been rejected at apply-time."""
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


def _discount_for(coupon, subtotal):
    subtotal = flt(subtotal)

    if coupon.discount_type == "Percentage":
        amount = subtotal * flt(coupon.discount_value) / 100
    else:
        amount = flt(coupon.discount_value)

    # Never below zero, and never more than the order itself.
    return round(min(max(amount, 0), subtotal), 2)


@frappe.whitelist(allow_guest=True)
def apply_coupon(code=None, subtotal=None):
    coupon = _get_valid_coupon(code)
    discount_amount = _discount_for(coupon, subtotal)

    return {
        "code": coupon.code,
        "discount_type": coupon.discount_type,
        "discount_value": coupon.discount_value,
        "discount_amount": discount_amount,
    }


def calculate_checkout_discount(code, subtotal):
    """Used by create_checkout_session() itself - returns (discount_amount,
    coupon_doc) rather than throwing, so an invalid/expired code that
    somehow reaches here just applies no discount instead of blocking
    the whole checkout."""
    if not code:
        return 0, None

    try:
        coupon = _get_valid_coupon(code)
    except frappe.ValidationError:
        return 0, None

    return _discount_for(coupon, subtotal), coupon


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

@frappe.whitelist()
def get_coupons():
    _ensure_store_access()

    return frappe.get_all(
        COUPON_DOCTYPE,
        fields=COUPON_LIST_FIELDS,
        order_by="creation desc",
    )


@frappe.whitelist()
def create_coupon(code=None, discount_type=None, discount_value=None, active=1, expiry_date=None, max_uses=0, description=None):
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
    coupon.expiry_date = expiry_date or None
    coupon.max_uses = cint(max_uses)
    coupon.description = description or ""
    coupon.insert(ignore_permissions=True)
    frappe.db.commit()

    return {"ok": 1, "name": coupon.name}


@frappe.whitelist()
def update_coupon(name=None, discount_type=None, discount_value=None, active=None, expiry_date=None, max_uses=None, description=None):
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
