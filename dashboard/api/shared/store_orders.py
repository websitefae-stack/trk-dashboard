"""
Store order fulfilment - the "Orders" section of the Store dashboard.
Webshop Checkout is the order record itself (see webshop_purchase.py's
_fulfil_checkout_session): it starts life as a cart, flips to "Paid" once
Stripe confirms payment, and this module adds the two steps after that -
"Packed" and "Shipped" - a Store Manager works through once a paid order
actually needs picking, packing and posting.
"""

import frappe
from frappe import _
from frappe.utils import now_datetime, nowdate

from dashboard.api.shared.store_products import _ensure_store_access, _to_int

ORDER_DOCTYPE = "Webshop Checkout"

# "Pending" checkouts are abandoned/incomplete carts that never actually
# paid - never shown as an order at all.
ORDER_STATUSES = ["Paid", "Packed", "Shipped"]


def _variant_label(item_code):
    attr_rows = frappe.get_all(
        "Item Variant Attribute",
        filters={"parent": item_code, "parenttype": "Item"},
        fields=["attribute", "attribute_value"],
        order_by="idx asc",
    )

    if not attr_rows:
        return ""

    return ", ".join(f"{row.attribute}: {row.attribute_value}" for row in attr_rows)


def _order_totals(checkout_name):
    rows = frappe.get_all(
        "Webshop Checkout Item",
        filters={"parent": checkout_name, "parenttype": ORDER_DOCTYPE},
        fields=["qty", "rate", "currency"],
    )

    total = sum((row.qty or 0) * (row.rate or 0) for row in rows)
    item_count = sum(row.qty or 0 for row in rows)
    currency = rows[0].currency if rows else "GBP"

    return total, item_count, currency


@frappe.whitelist()
def get_store_orders(search=None, status=None):
    _ensure_store_access()

    status = (status or "").strip()
    statuses = [status] if status in ORDER_STATUSES else ORDER_STATUSES

    filters = {"status": ["in", statuses]}

    search = (search or "").strip()
    if search:
        filters["full_name"] = ["like", f"%{search}%"]

    orders = frappe.get_all(
        ORDER_DOCTYPE,
        filters=filters,
        fields=[
            "name", "full_name", "email", "phone", "status", "creation",
            "city", "postcode", "invoice", "packed_on", "shipped_on", "tracking_number",
        ],
        order_by="creation desc",
        limit_page_length=1000,
    )

    if search:
        # full_name is already filtered server-side above - email is
        # covered here too since Data fields can't cheaply OR-filter
        # alongside a Data like-filter in one frappe.get_all call.
        matching_emails = frappe.get_all(
            ORDER_DOCTYPE,
            filters={"status": ["in", statuses], "email": ["like", f"%{search}%"]},
            fields=[
                "name", "full_name", "email", "phone", "status", "creation",
                "city", "postcode", "invoice", "packed_on", "shipped_on", "tracking_number",
            ],
            order_by="creation desc",
            limit_page_length=1000,
        )

        seen_names = {row.name for row in orders}
        for row in matching_emails:
            if row.name not in seen_names:
                orders.append(row)
                seen_names.add(row.name)

        orders.sort(key=lambda row: row.creation, reverse=True)

    result = []

    for order in orders:
        total, item_count, currency = _order_totals(order.name)

        result.append({
            "name": order.name,
            "full_name": order.full_name,
            "email": order.email,
            "phone": order.phone or "",
            "status": order.status,
            "creation": str(order.creation),
            "city": order.city or "",
            "postcode": order.postcode or "",
            "invoice": order.invoice or "",
            "packed_on": str(order.packed_on or ""),
            "shipped_on": str(order.shipped_on or ""),
            "tracking_number": order.tracking_number or "",
            "item_count": item_count,
            "total": total,
            "currency": currency,
        })

    return result


@frappe.whitelist()
def get_store_order(name=None):
    _ensure_store_access()

    name = (name or "").strip()

    if not name or not frappe.db.exists(ORDER_DOCTYPE, name):
        frappe.throw(_("Order not found."))

    order = frappe.get_doc(ORDER_DOCTYPE, name)

    if order.status not in ORDER_STATUSES:
        frappe.throw(_("This checkout was never paid, so it isn't an order."))

    items = []
    total = 0

    item_meta = frappe.get_meta("Item")
    item_fields = ["image"]
    if item_meta.has_field("custom_sku"):
        item_fields.append("custom_sku")

    for row in order.items or []:
        amount = (row.qty or 0) * (row.rate or 0)
        total += amount

        item_info = frappe.db.get_value("Item", row.item_code, item_fields, as_dict=True) or {}

        items.append({
            "item_code": row.item_code,
            "item_name": row.item_name,
            "variant_label": _variant_label(row.item_code),
            "image": item_info.get("image") or "",
            "sku": item_info.get("custom_sku") or "",
            "qty": row.qty,
            "rate": row.rate,
            "amount": amount,
            "currency": row.currency or "GBP",
        })

    return {
        "name": order.name,
        "status": order.status,
        "creation": str(order.creation),
        "full_name": order.full_name,
        "email": order.email,
        "phone": order.phone or "",
        "coach": order.coach or "",
        "address_line1": order.address_line1 or "",
        "address_line2": order.address_line2 or "",
        "city": order.city or "",
        "postcode": order.postcode or "",
        "country": order.country or "",
        "invoice": order.invoice or "",
        "packed_on": str(order.packed_on or ""),
        "shipped_on": str(order.shipped_on or ""),
        "tracking_number": order.tracking_number or "",
        "items": items,
        "total": total,
        "currency": items[0]["currency"] if items else "GBP",
    }


@frappe.whitelist()
def mark_order_packed(name=None):
    _ensure_store_access()

    name = (name or "").strip()

    if not name or not frappe.db.exists(ORDER_DOCTYPE, name):
        frappe.throw(_("Order not found."))

    status = frappe.db.get_value(ORDER_DOCTYPE, name, "status")

    if status not in ("Paid", "Packed"):
        frappe.throw(_("Only a paid order can be marked as packed."))

    frappe.db.set_value(ORDER_DOCTYPE, name, {
        "status": "Packed",
        "packed_on": now_datetime(),
    })
    frappe.db.commit()

    return {"ok": 1}


@frappe.whitelist()
def mark_order_shipped(name=None, tracking_number=None):
    _ensure_store_access()

    name = (name or "").strip()

    if not name or not frappe.db.exists(ORDER_DOCTYPE, name):
        frappe.throw(_("Order not found."))

    status = frappe.db.get_value(ORDER_DOCTYPE, name, "status")

    if status not in ("Paid", "Packed", "Shipped"):
        frappe.throw(_("This order can't be marked as shipped."))

    updates = {"status": "Shipped", "shipped_on": now_datetime()}

    tracking_number = (tracking_number or "").strip()
    if tracking_number:
        updates["tracking_number"] = tracking_number

    frappe.db.set_value(ORDER_DOCTYPE, name, updates)
    frappe.db.commit()

    return {"ok": 1}
