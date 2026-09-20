"""
Guest-facing checkout for one-off online purchases (services, products,
merch) - deliberately separate from the stock Frappe webshop app (its
checkout hard-requires a login, which is exactly the problem this
replaces).

Mirrors the guest-facing shape already established by public_booking.py:
a no-login Jinja page in resilient_domains, paired with
@frappe.whitelist(allow_guest=True) endpoints here. "Buy Now" only -
browsing/product display stays wherever the item is already shown.

Price is always computed here from the Item's own Item Price, never
trusted from the browser - the client only ever sends an item_code and
a quantity.

Every purchase is routed onto a real Client, not kept in a separate
"Online Client" silo (that used to be the design - an online purchase
never mixed into the real Client list, Ashley linked the two manually
by email later - deliberately changed so an existing client's purchase
shows up in the same client_portal login they already use, and a new
buyer gets their own portal access automatically instead of a second,
disconnected identity). The Online Client record is still created too,
purely as the same lightweight admin-facing record it always was -
nothing currently reads it for portal access.
"""

import frappe
from frappe import _
from frappe.utils import nowdate, fmt_money, get_url

from dashboard.dashboard.doctype.webshop_payment_settings.webshop_payment_settings import get_settings
from dashboard.api.shared.email_templates import plain_text_to_email_html
from dashboard.api.shared.item_access import _get_coach_login, COACH_ONLY_PRICE_LIST
from dashboard.api.shared.invoices import _get_bank_account_gl_account, _get_current_coach, _coach_label
from dashboard.api.shared.store_products import _get_coach_price
from dashboard.api.shared import payment_utils
from dashboard.api.shared.email_groups import add_to_email_group
from dashboard.api.shared.store_coupons import calculate_checkout_discount, record_coupon_use
from dashboard.api.shared.notifications import create_trk_notification, FRANCHISOR_USERS

ONLINE_CLIENT_DOCTYPE = "Online Client"
WEBSHOP_CUSTOMERS_EMAIL_GROUP = "Website Customers"


def _is_current_user_coach():
    """
    Guest-safe - unlike permissions.get_current_coach_name(), never
    throws for an anonymous checkout (the overwhelming majority of
    these), it just says False. A coach who's actually logged in while
    buying (e.g. via the Coach Store) carries the same session here, so
    this is the one server-side source of truth for "does this buyer get
    the coach price / Coach Only items" - never trust anything the
    browser sends for this.
    """
    user = frappe.session.user
    if not user or user == "Guest":
        return False
    return bool(frappe.db.exists("Coach", {"user": user}) or frappe.db.exists("Coach", {"coach_email": user}))

# The Table fieldname add_client_contact_link_table_field.py (client_portal
# app) added to Client - not imported from that app (this app never
# imports another app's Python, only reads/writes the same core doctypes
# directly), just the same fixed fieldname that patch created.
CLIENT_CONTACT_LINK_PARENTFIELD = "client_contact_link"

# Only the view-level permissions a webshop buyer needs to see their own
# purchases/downloads - never can_manage_staff_access or edit-type
# permissions, which stay something office grants by hand.
PORTAL_PERMISSIONS_FOR_BUYER = [
    "view_profile",
    "can_view_invoices",
    "can_view_courses_and_products",
    "can_view_downloads",
]

# The four brand logos a buyer can pick between for a sleeve/leg-print
# product (Item.custom_logo_choice_enabled) - fixed, store-wide, never
# per-product (see the Store Logo Choice single doctype). key is what's
# actually stored against the cart line/order; label/fieldname are just
# how it's shown and where its image lives on that single doc.
LOGO_CHOICE_DOCTYPE = "Store Logo Choice"
LOGO_CHOICES = [
    {"key": "Kid", "label": "The Resilient Kid", "fieldname": "kid_logo"},
    {"key": "Teen", "label": "The Resilient Teen", "fieldname": "teen_logo"},
    {"key": "People", "label": "The Resilient People", "fieldname": "people_logo"},
    {"key": "School", "label": "The Resilient School", "fieldname": "school_logo"},
]


def _logo_choice_label(key):
    for choice in LOGO_CHOICES:
        if choice["key"] == key:
            return choice["label"]
    return key


@frappe.whitelist(allow_guest=True)
def get_logo_choice_options():
    """The four brand logos, with whichever image has been uploaded for
    each on the Store Logo Choice single doc - used both by the public
    /buy page (to show what each logo looks like) and by the Store
    dashboard's own settings panel for uploading them."""
    if not frappe.db.exists("DocType", LOGO_CHOICE_DOCTYPE):
        return []

    values = frappe.db.get_singles_dict(LOGO_CHOICE_DOCTYPE)

    return [
        {"key": choice["key"], "label": choice["label"], "image": values.get(choice["fieldname"]) or ""}
        for choice in LOGO_CHOICES
    ]


def _get_stripe_secret_key(settings):
    """
    Reuses whichever existing Stripe Settings record Webshop Payment
    Settings.stripe_settings points at (Setup > Integrations > Stripe
    Settings, a core Frappe/ERPNext doctype - this app never creates its
    own Stripe account/key, only reuses the one already stored there).
    """
    if not settings.stripe_settings:
        return ""

    if not frappe.db.exists("Stripe Settings", settings.stripe_settings):
        return ""

    stripe_settings_doc = frappe.get_doc("Stripe Settings", settings.stripe_settings)

    return stripe_settings_doc.get_password("secret_key", raise_exception=False)


def _to_float(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _split_full_name(full_name):
    parts = (full_name or "").strip().split()

    if not parts:
        return "", ""

    return parts[0], " ".join(parts[1:])


def _parse_cart_items(items):
    """items is a JSON-encoded (or already-parsed, same as any other
    fetch() POST body) list of {"item_code": ..., "qty": ..., "personalization": ..., "logo_choice": ...}
    - a single "Buy Now" is just a one-item cart, so every checkout goes
    through this same shape. personalization/logo_choice are never
    validated here against the item's own enabled flags (a stray value
    on an item that doesn't offer either is harmless, just an extra note
    nobody reads), only length-capped so it can't be used to stuff
    something huge into an invoice line."""
    raw = items

    if isinstance(raw, str):
        try:
            raw = frappe.parse_json(raw)
        except Exception:
            raw = []

    if not isinstance(raw, list):
        return []

    parsed = []

    for entry in raw:
        if not isinstance(entry, dict):
            continue

        item_code = (entry.get("item_code") or "").strip()
        qty = max(1, int(_to_float(entry.get("qty")) or 1))
        personalization = (entry.get("personalization") or "").strip()[:140]
        logo_choice = (entry.get("logo_choice") or "").strip()[:40]

        if item_code:
            parsed.append({
                "item_code": item_code,
                "qty": qty,
                "personalization": personalization,
                "logo_choice": logo_choice,
            })

    return parsed


def _default_price_list_for_item(item_code, company):
    return frappe.db.get_value(
        "Item Default", {"parent": item_code, "parenttype": "Item", "company": company}, "default_price_list"
    )


def _get_purchasable_item(item_code, company):
    if not item_code or not frappe.db.exists("Item", item_code):
        frappe.throw(_("Item not found."))

    item_default = frappe.db.get_value(
        "Item Default",
        {"parent": item_code, "parenttype": "Item", "company": company},
        ["default_price_list", "custom_show_on_site"],
        as_dict=True,
    )

    if not item_default or not item_default.get("custom_show_on_site"):
        frappe.throw(_("This item is not available for online purchase."))

    item_doc = frappe.get_doc("Item", item_code)
    is_coach = _is_current_user_coach()

    # "Coach Only" items simply aren't available for anyone else to buy -
    # same wording as the "not shown on site" case above, doesn't hint
    # that a coach-only version exists.
    if (item_doc.get("custom_item_visibility") or "Everyone") == "Coach Only" and not is_coach:
        frappe.throw(_("This item is not available for online purchase."))

    price_list = item_default.get("default_price_list")
    rate = 0
    currency = "GBP"

    # A coach's own fixed price (only ever set deliberately per item -
    # see store_products.py's _get_coach_price()) wins over the normal
    # price list; falls straight through to it when there isn't one. For
    # a variant (e.g. one size of a hoodie), the coach price always lives
    # on the template, never the variant itself - a coach pays the same
    # set amount no matter which size/colour they buy, unlike the regular
    # price which does vary by variant. _get_coach_price() itself knows
    # a template can never hold an Item Price row (core Frappe rejects
    # that outright) and reads its custom_coach_price field instead.
    if is_coach:
        coach_price_item_code = item_doc.get("variant_of") or item_code
        coach_price = _get_coach_price(coach_price_item_code)
        if coach_price:
            rate = coach_price
            currency = "GBP"

    if not rate and price_list:
        price_rows = frappe.get_all(
            "Item Price",
            filters={"item_code": item_code, "price_list": price_list, "selling": 1},
            fields=["price_list_rate", "currency"],
            order_by="valid_from desc, modified desc",
            limit_page_length=1,
            ignore_permissions=True,
        )

        if price_rows:
            rate = price_rows[0].get("price_list_rate") or 0
            currency = price_rows[0].get("currency") or currency

    if not rate:
        frappe.throw(_("This item doesn't have a price set for online purchase yet."))

    # Only Store products carry a stock concept at all (custom_stock_qty/
    # custom_unlimited_stock default to 0/unticked on every Item, store
    # product or not - gating on custom_store_enabled here keeps this
    # from blocking an unrelated one-off purchase, e.g. a coaching
    # service or course, that was never meant to track stock).
    if (
        item_doc.get("custom_store_enabled")
        and not item_doc.get("custom_unlimited_stock")
        and (item_doc.get("custom_stock_qty") or 0) <= 0
    ):
        frappe.throw(_("{0} is currently out of stock.").format(item_doc.item_name or item_code))

    return {
        "item_code": item_code,
        "item_name": item_doc.item_name or item_code,
        "description": item_doc.description or "",
        "image": item_doc.image or "",
        "gallery": [row.image for row in (item_doc.get("custom_gallery") or []) if row.image],
        "rate": rate,
        "currency": currency,
        "price_list": price_list,
        "personalization_enabled": bool(item_doc.get("custom_personalization_enabled")),
        "personalization_label": item_doc.get("custom_personalization_label") or "",
        "logo_choice_enabled": bool(item_doc.get("custom_logo_choice_enabled")),
    }


@frappe.whitelist(allow_guest=True)
def get_purchasable_item(item_code=None):
    """Public product-page lookup - price/availability only, no personal data collected here."""
    settings = get_settings()

    if not settings.enabled:
        frappe.throw(_("Online checkout isn't available right now."))

    item = _get_purchasable_item((item_code or "").strip(), settings.company)

    return {
        "item_code": item["item_code"],
        "item_name": item["item_name"],
        "description": item["description"],
        "image": item["image"],
        "gallery": item["gallery"],
        "rate": item["rate"],
        "currency": item["currency"],
        "personalization_enabled": item["personalization_enabled"],
        "personalization_label": item["personalization_label"],
        "logo_choice_enabled": item["logo_choice_enabled"],
    }


@frappe.whitelist(allow_guest=True)
def get_item_or_variants(item_code=None):
    """
    Public checkout-page lookup that also handles a variant template
    (Item.has_variants=1, e.g. "Summer Resilience Support" sold in a few
    different age-group/length options) - the checkout page can't just
    price it directly the way get_purchasable_item() does a plain item,
    since a template is never itself directly sellable; the actual price
    only exists on each of its real variant Items.

    Returns {"is_template": False, "item": {...}} for a plain item
    (identical shape to get_purchasable_item()), or {"is_template": True,
    "item_name", "description", "attributes": [...], "variants": [...]}
    for a template - "attributes" is what to prompt for (one dropdown
    per entry), "variants" is every currently purchasable variant with
    its own attribute values and price, so the browser can resolve a
    full selection to one specific item_code and rate without a second
    round-trip. Skips (rather than errors on) any variant that isn't
    actually available for online purchase yet - a template with at
    least one purchasable variant should still work even if others
    aren't priced/shown-on-site yet.
    """
    settings = get_settings()

    if not settings.enabled:
        frappe.throw(_("Online checkout isn't available right now."))

    item_code = (item_code or "").strip()

    if not item_code or not frappe.db.exists("Item", item_code):
        frappe.throw(_("Item not found."))

    item_doc = frappe.get_doc("Item", item_code)

    if not item_doc.has_variants:
        item = _get_purchasable_item(item_code, settings.company)
        return {
            "is_template": False,
            "item": {
                "item_code": item["item_code"],
                "item_name": item["item_name"],
                "description": item["description"],
                "image": item["image"],
                "gallery": item["gallery"],
                "rate": item["rate"],
                "currency": item["currency"],
                "personalization_enabled": item["personalization_enabled"],
                "personalization_label": item["personalization_label"],
                "logo_choice_enabled": item["logo_choice_enabled"],
            },
        }

    variant_rows = frappe.get_all(
        "Item",
        filters={"variant_of": item_code, "disabled": 0},
        fields=["name"],
        limit_page_length=500,
    )

    attribute_names = []
    attribute_values = {}
    variants = []

    for row in variant_rows:
        try:
            purchasable = _get_purchasable_item(row.name, settings.company)
        except Exception:
            # Not priced/shown-on-site for this company yet, or out of
            # stock - skip it rather than fail the whole template.
            continue

        attr_rows = frappe.get_all(
            "Item Variant Attribute",
            filters={"parent": row.name, "parenttype": "Item"},
            fields=["attribute", "attribute_value"],
            order_by="idx asc",
        )

        attrs = {}

        for attr_row in attr_rows:
            attrs[attr_row.attribute] = attr_row.attribute_value

            if attr_row.attribute not in attribute_names:
                attribute_names.append(attr_row.attribute)

            attribute_values.setdefault(attr_row.attribute, [])

            if attr_row.attribute_value not in attribute_values[attr_row.attribute]:
                attribute_values[attr_row.attribute].append(attr_row.attribute_value)

        variants.append({
            "item_code": row.name,
            "attributes": attrs,
            "item_name": purchasable["item_name"],
            "description": purchasable["description"],
            # Falls back to the template's own image when this specific
            # variant has none of its own - not every attribute-value
            # combination gets a dedicated photo uploaded (see the "one
            # photo per attribute value" system in store_products.py), so
            # without this a variant with no photo of its own would show
            # blank instead of at least the template's shot.
            "image": purchasable["image"] or item_doc.image or "",
            "rate": purchasable["rate"],
            "currency": purchasable["currency"],
        })

    if not variants:
        frappe.throw(_("This item isn't available for online purchase yet."))

    # The gallery strip shown on /buy for a template product - its own
    # uploaded extra photos plus every distinct variant photo (so a
    # shopper can browse what each size/style/colour actually looks like
    # before picking one), deduplicated in that order.
    gallery = [row.image for row in (item_doc.get("custom_gallery") or []) if row.image]
    seen_images = set(gallery)
    for variant in variants:
        variant_image = variant.get("image")
        if variant_image and variant_image not in seen_images:
            seen_images.add(variant_image)
            gallery.append(variant_image)

    return {
        "is_template": True,
        "item_name": item_doc.item_name or item_code,
        "description": item_doc.description or "",
        "image": item_doc.image or "",
        "gallery": gallery,
        "personalization_enabled": bool(item_doc.get("custom_personalization_enabled")),
        "personalization_label": item_doc.get("custom_personalization_label") or "",
        "logo_choice_enabled": bool(item_doc.get("custom_logo_choice_enabled")),
        "attributes": [
            {"attribute": name, "values": attribute_values.get(name, [])}
            for name in attribute_names
        ],
        "variants": variants,
    }


@frappe.whitelist(allow_guest=True)
def create_checkout_session(
    items=None,
    full_name=None,
    email=None,
    phone=None,
    address_line1=None,
    address_line2=None,
    city=None,
    postcode=None,
    country=None,
    coach=None,
    coupon_code=None,
    success_url=None,
    cancel_url=None,
):
    """
    items is a list (or JSON-encoded list) of {"item_code", "qty"} - a
    single "Buy Now" and a full multi-item cart both go through this one
    path, each item's price always recomputed here from its own Item
    Price (see module docstring), never trusted from the browser.

    The cart itself (contact details + resolved item/price lines) is
    saved as a Webshop Checkout doc before Stripe is even called, and
    only that doc's name goes into the Stripe session's metadata - the
    webhook re-reads the real doc rather than trying to fit a whole cart
    into Stripe's small per-field metadata size limit.
    """
    settings = get_settings()

    if not settings.enabled:
        frappe.throw(_("Online checkout isn't available right now."))

    stripe_secret_key = _get_stripe_secret_key(settings)

    if not stripe_secret_key:
        frappe.throw(_("Online checkout isn't fully set up yet."))

    cart_lines = _parse_cart_items(items)

    if not cart_lines:
        frappe.throw(_("Your cart is empty."))

    full_name = (full_name or "").strip()
    email = (email or "").strip()

    if not full_name:
        frappe.throw(_("Full name is required."))

    if not email:
        frappe.throw(_("Email is required."))

    coach = (coach or "").strip()
    if coach and not frappe.db.exists("Coach", coach):
        coach = ""

    checkout = frappe.new_doc("Webshop Checkout")
    checkout.full_name = full_name
    checkout.email = email
    checkout.phone = phone or ""
    checkout.address_line1 = address_line1 or ""
    checkout.address_line2 = address_line2 or ""
    checkout.city = city or ""
    checkout.postcode = postcode or ""
    checkout.country = country or ""
    checkout.coach = coach or None

    line_items = []
    priced_lines = []

    for line in cart_lines:
        item = _get_purchasable_item(line["item_code"], settings.company)
        unit_amount = int(round(_to_float(item["rate"]) * 100))

        if unit_amount <= 0:
            frappe.throw(_("{0} cannot be purchased online right now.").format(item["item_name"]))

        priced_lines.append({"item_code": item["item_code"], "qty": line["qty"], "price": item["rate"]})

        checkout.append("items", {
            "item_code": item["item_code"],
            "item_name": item["item_name"],
            "qty": line["qty"],
            "rate": item["rate"],
            "currency": item["currency"],
            "personalization": line.get("personalization") or "",
            "logo_choice": line.get("logo_choice") or "",
        })

        line_items.append({
            "price_data": {
                "currency": (item["currency"] or "GBP").lower(),
                "product_data": {"name": item["item_name"]},
                "unit_amount": unit_amount,
            },
            "quantity": line["qty"],
        })

    # Re-validated here rather than trusted from the browser - a coupon
    # is only ever honoured at the amount/eligibility (including which
    # items it actually applies to) this same check would allow right now.
    discount_amount, coupon = calculate_checkout_discount(coupon_code, priced_lines)

    if coupon:
        checkout.coupon_code = coupon.code
        checkout.discount_amount = discount_amount

    checkout.insert(ignore_permissions=True)
    frappe.db.commit()

    import stripe

    stripe.api_key = stripe_secret_key

    session_kwargs = dict(
        mode="payment",
        payment_method_types=["card"],
        customer_email=email,
        line_items=line_items,
        # Reconstructed server-side by the webhook once payment actually
        # succeeds - nothing here is trusted, this is only how the cart
        # survives the redirect to Stripe and back.
        metadata={"checkout": checkout.name},
        success_url=success_url or (get_url() + "/order-confirmed?session_id={CHECKOUT_SESSION_ID}"),
        cancel_url=cancel_url or get_url(),
    )

    if discount_amount > 0:
        # A one-off Stripe Coupon applied just to this session - line
        # item amounts stay untouched (Stripe doesn't allow negative
        # line items), Stripe applies the reduction itself at charge time.
        stripe_coupon = stripe.Coupon.create(
            amount_off=int(round(discount_amount * 100)),
            currency=line_items[0]["price_data"]["currency"],
            duration="once",
            name=f"Discount ({coupon.code})",
        )
        session_kwargs["discounts"] = [{"coupon": stripe_coupon.id}]

    checkout_session = stripe.checkout.Session.create(**session_kwargs)

    checkout.stripe_session_id = checkout_session.id
    checkout.save(ignore_permissions=True)
    frappe.db.commit()

    return {"checkout_url": checkout_session.url}


def _send_coach_order_confirmation_email(invoice, coach_email, coach_display_name, order_lines, settings):
    amount_display = fmt_money(invoice.grand_total, currency=invoice.currency)

    order_lines_text = "\n".join(
        f"{line['item_name']} x{line['qty']} - "
        f"{fmt_money((line['rate'] or 0) * (line['qty'] or 1), currency=line['currency'] or invoice.currency)}"
        for line in order_lines
    )

    message = (
        f"Hi {coach_display_name},\n"
        "\n"
        "Thanks for your order from the Coach Store - here's your invoice.\n"
        "\n"
        f"{order_lines_text}\n"
        "\n"
        f"Total: {amount_display}\n"
        "\n"
        f"Order reference: {invoice.name}\n"
        "\n"
        "Warm regards,\n"
        f"{settings.company}"
    )

    cc = [settings.office_notification_email] if settings.office_notification_email else []

    frappe.sendmail(
        recipients=[coach_email],
        cc=cc,
        subject=f"Coach Store order confirmation - {invoice.name}",
        message=plain_text_to_email_html(message),
        attachments=[frappe.attach_print("Sales Invoice", invoice.name, letterhead="Resilient Kid")],
        now=True,
        reference_doctype="Sales Invoice",
        reference_name=invoice.name,
    )


@frappe.whitelist()
def create_coach_store_order(items=None):
    """
    The Coach Store's own "Place Order" - deliberately not the guest
    checkout above (no Stripe, no contact-detail form, no Online Client/
    portal-access machinery): a coach placing this is already a known,
    logged-in identity, so this just prices the cart server-side (the
    same _get_purchasable_item() every other purchase goes through, so
    Coach Only visibility/coach pricing is enforced exactly the same
    way), raises a Sales Invoice under the same Company as every other
    online order, and emails it to the coach and to the office - nothing
    else, no payment step.

    Deliberately NOT allow_guest - a Guest is already rejected by the
    framework before this even runs, and _get_current_coach() below
    additionally rejects any other logged-in user (e.g. a client_portal
    login) that isn't actually a Coach - only a real coach's own session
    can ever place an order here.
    """
    coach = _get_current_coach()

    if not coach:
        frappe.throw(_("Only a coach can place an order here."), frappe.PermissionError)

    settings = get_settings()

    if not settings.enabled or not settings.company:
        frappe.throw(_("Online checkout isn't available right now."))

    cart_lines = _parse_cart_items(items)

    if not cart_lines:
        frappe.throw(_("Your order is empty."))

    coach_email = frappe.session.user
    coach_display_name = _coach_label(coach) or coach_email

    customer_name = _get_or_create_customer_for_contact(coach_email, coach_display_name)

    invoice = frappe.new_doc("Sales Invoice")
    invoice.customer = customer_name
    invoice.company = settings.company
    invoice.posting_date = nowdate()
    invoice.due_date = nowdate()

    if invoice.meta.has_field("custom_coach"):
        invoice.custom_coach = coach.get("name")

    price_list = None
    order_lines = []

    for line in cart_lines:
        item = _get_purchasable_item(line["item_code"], settings.company)

        if price_list is None:
            price_list = item.get("price_list")

        invoice.append("items", {
            "item_code": item["item_code"],
            "item_name": item["item_name"],
            "qty": line["qty"],
            "rate": item["rate"],
        })

        order_lines.append({
            "item_name": item["item_name"],
            "qty": line["qty"],
            "rate": item["rate"],
            "currency": item["currency"],
        })

    if price_list:
        invoice.selling_price_list = price_list

    if hasattr(invoice, "set_missing_values"):
        invoice.set_missing_values()
    if hasattr(invoice, "calculate_taxes_and_totals"):
        invoice.calculate_taxes_and_totals()

    invoice.insert(ignore_permissions=True)
    invoice.submit()
    frappe.db.commit()

    try:
        _send_coach_order_confirmation_email(invoice, coach_email, coach_display_name, order_lines, settings)
    except Exception:
        # The order/invoice is already raised - a failed email shouldn't
        # look like a failed order to the coach placing it.
        frappe.log_error(frappe.get_traceback(), f"Coach Store Order Confirmation Email Failed - {invoice.name}")

    _notify_coach_store_order(invoice, coach, coach_email, coach_display_name)

    return {"ok": 1, "invoice": invoice.name}


def _notify_coach_store_order(invoice, coach, coach_email, coach_display_name):
    """
    In-app notifications alongside the email above - the coach sees their
    own order confirmed in their notifications, and every franchisor
    admin (FRANCHISOR_USERS) sees it too, with a nudge to actually ship
    it (this is the only place that happens - nothing here talks to a
    courier/fulfilment system). Best-effort, same reasoning as the email
    just above: a broken notification must never look like a failed order.
    """
    try:
        create_trk_notification(
            recipient_user=coach_email,
            notification_type="Task",
            message=f"Your Coach Store order has been placed - invoice {invoice.name}.",
            reference_doctype="Sales Invoice",
            reference_name=invoice.name,
            coach=coach.get("name"),
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Coach Store Order Notification (Coach) Failed - {invoice.name}")

    for admin_user in FRANCHISOR_USERS:
        if not frappe.db.exists("User", admin_user):
            continue

        try:
            create_trk_notification(
                recipient_user=admin_user,
                notification_type="Task",
                message=(
                    f"{coach_display_name} placed a Coach Store order - invoice {invoice.name} "
                    "created. Please ship the order."
                ),
                priority="High",
                reference_doctype="Sales Invoice",
                reference_name=invoice.name,
            )
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Coach Store Order Notification (Franchisor) Failed - {invoice.name}")


def _get_or_create_online_client(
    full_name, email, phone, address_line1, address_line2, city, postcode, country, coach,
):
    existing_name = frappe.db.get_value(ONLINE_CLIENT_DOCTYPE, {"email": email}, "name")

    if existing_name:
        doc = frappe.get_doc(ONLINE_CLIENT_DOCTYPE, existing_name)
    else:
        doc = frappe.new_doc(ONLINE_CLIENT_DOCTYPE)
        doc.email = email

    doc.full_name = full_name or doc.get("full_name") or email

    if phone:
        doc.phone = phone
    if address_line1:
        doc.address_line1 = address_line1
    if address_line2:
        doc.address_line2 = address_line2
    if city:
        doc.city = city
    if postcode:
        doc.postcode = postcode
    if country:
        doc.country = country
    if coach:
        doc.purchased_from_coach = coach

    doc.save(ignore_permissions=True)

    return doc.name


def _get_or_create_customer_for_contact(email, full_name, phone=None):
    """Finds (or creates) the Customer linked to this email's Contact -
    shared by the guest checkout (an Online Client's own details) and the
    coach store (a coach's own login email/name), since both ultimately
    just need "whoever is paying this Sales Invoice"."""
    existing_contact_name = frappe.db.get_value("Contact Email", {"email_id": email}, "parent")

    if existing_contact_name:
        contact = frappe.get_doc("Contact", existing_contact_name)
    else:
        first_name, last_name = _split_full_name(full_name)
        contact = frappe.new_doc("Contact")
        contact.first_name = first_name or email
        if last_name:
            contact.last_name = last_name
        contact.append("email_ids", {"email_id": email, "is_primary": 1})
        if phone:
            contact.append("phone_nos", {"phone": phone, "is_primary_mobile_no": 1})
        contact.insert(ignore_permissions=True)

    for link in contact.get("links") or []:
        if link.get("link_doctype") == "Customer" and frappe.db.exists("Customer", link.get("link_name")):
            return link.get("link_name")

    customer_doc = frappe.new_doc("Customer")
    customer_doc.customer_type = "Individual"
    customer_doc.customer_name = full_name or email
    customer_doc.insert(ignore_permissions=True)

    contact.append("links", {"link_doctype": "Customer", "link_name": customer_doc.name})
    contact.save(ignore_permissions=True)

    return customer_doc.name


def _set_if_field(doc, fieldname, value):
    if value is not None and frappe.get_meta(doc.doctype).has_field(fieldname):
        doc.set(fieldname, value)


def _get_or_create_portal_client(full_name, email, phone):
    """
    Finds the real coaching Client this email already belongs to, if any -
    an existing client buying something must land on their own existing
    record, never a second one. Creates a bare new Client only if truly
    nobody matches yet.
    """
    existing_name = frappe.db.get_value("Client", {"email": email}, "name")

    if existing_name:
        return existing_name, False

    first_name, last_name = _split_full_name(full_name)

    client = frappe.new_doc("Client")
    _set_if_field(client, "name1", first_name)
    _set_if_field(client, "last_name", last_name)
    _set_if_field(client, "full_name", full_name or email)
    _set_if_field(client, "preferred_name", first_name)
    _set_if_field(client, "email", email)
    _set_if_field(client, "mobile", phone)
    _set_if_field(client, "status", "Active")
    _set_if_field(client, "client_type", "Adult")
    client.insert(ignore_permissions=True)

    return client.name, True


def _ensure_portal_login(email, full_name):
    """Creates the login itself - Frappe's own welcome email handles
    setting a password, nothing here ever sets or knows one."""
    if frappe.db.exists("User", email):
        return False

    first_name, last_name = _split_full_name(full_name)

    user = frappe.new_doc("User")
    user.email = email
    user.first_name = first_name or email
    if last_name:
        user.last_name = last_name
    user.user_type = "Website User"
    user.enabled = 1
    user.send_welcome_email = 1
    user.insert(ignore_permissions=True)

    return True


def _ensure_portal_access(client_name, contact_name, email):
    """
    Grants this email access to its own Client's client_portal login -
    the same Client Contact Link child table client_portal's own
    invitation flow writes to, just skipping the invite/accept step since
    a completed, paid purchase is already a stronger signal of ownership
    than an emailed invite link. Does nothing if client_portal isn't
    installed on this site, or this email already has access.
    """
    client_meta = frappe.get_meta("Client")

    if not client_meta.has_field(CLIENT_CONTACT_LINK_PARENTFIELD):
        return False

    client_doc = frappe.get_doc("Client", client_name)

    for row in client_doc.get(CLIENT_CONTACT_LINK_PARENTFIELD) or []:
        if (row.get("email_id") or "").strip().lower() == email:
            return False

    contact_first_name = frappe.db.get_value("Contact", contact_name, "first_name") if contact_name else None

    row = client_doc.append(CLIENT_CONTACT_LINK_PARENTFIELD, {})
    row.contact = contact_name
    row.contact_name = contact_first_name or email
    row.email_id = email
    row.is_primary_contact = 1
    row.portal_access_enabled = 1

    for fieldname in PORTAL_PERMISSIONS_FOR_BUYER:
        if row.meta.has_field(fieldname):
            row.set(fieldname, 1)

    client_doc.save(ignore_permissions=True)

    return True


def _unlock_courses_for_purchase(email, item_codes):
    """Any purchased item with custom_unlocks_lms_course set enrols the
    buyer in that course automatically, same LMS Enrollment shape
    resilient_domains' course_signup.py creates for a direct signup."""
    if not frappe.db.exists("DocType", "LMS Course"):
        return []

    item_meta = frappe.get_meta("Item")
    if not item_meta.has_field("custom_unlocks_lms_course"):
        return []

    unlocked = []

    for item_code in item_codes:
        course = frappe.db.get_value("Item", item_code, "custom_unlocks_lms_course")
        if not course:
            continue

        already_enrolled = frappe.db.exists("LMS Enrollment", {"course": course, "member": email})
        if already_enrolled:
            continue

        enrollment = frappe.new_doc("LMS Enrollment")
        enrollment.course = course
        enrollment.member = email
        enrollment.insert(ignore_permissions=True)
        unlocked.append(course)

    return unlocked


def _send_order_confirmation_emails(
    invoice, online_client, checkout_items, settings, coach,
    digital_files=None, granted_new_portal_access=False, unlocked_courses=None,
    coupon_code=None, discount_amount=0,
):
    amount_display = fmt_money(invoice.grand_total, currency=invoice.currency)

    order_lines = "\n".join(
        f"{line.item_name} x{line.qty} - "
        f"{fmt_money((line.rate or 0) * (line.qty or 1), currency=line.currency or invoice.currency)}"
        + (f" (Personalization: {line.personalization})" if line.get("personalization") else "")
        + (f" (Logo: {_logo_choice_label(line.logo_choice)})" if line.get("logo_choice") else "")
        for line in checkout_items
    )

    discount_line = ""
    if discount_amount:
        discount_display = fmt_money(discount_amount, currency=invoice.currency)
        discount_line = f"Discount ({coupon_code}): -{discount_display}\n"

    message = (
        f"Hi {online_client.full_name},\n"
        "\n"
        "Thanks for your order - here's your confirmation.\n"
        "\n"
        f"{order_lines}\n"
        "\n"
        f"{discount_line}"
        f"Total: {amount_display}\n"
        "\n"
        f"Order reference: {invoice.name}\n"
    )

    if digital_files:
        message += "\nDownloads:\n" + "\n".join(
            f"{file.get('item_name')}: {get_url(file.get('url'))}" for file in digital_files
        ) + "\n"

    if unlocked_courses:
        message += "\nYou now have access to: " + ", ".join(unlocked_courses) + "\n"

    if granted_new_portal_access:
        message += (
            "\nWe've also set up your client portal, where you can see this order and any "
            f"downloads any time - look out for a separate email to set your password, then log in at "
            f"{get_url('/trh-login')}\n"
        )

    message += (
        "\n"
        "Warm regards,\n"
        f"{settings.company}"
    )

    cc = set()

    if settings.office_notification_email:
        cc.add(settings.office_notification_email)

    if coach:
        coach_login = _get_coach_login(coach)
        if coach_login:
            cc.add(coach_login)

    subject_item = checkout_items[0].item_name if len(checkout_items) == 1 else f"{len(checkout_items)} items"

    frappe.sendmail(
        recipients=[online_client.email],
        cc=list(cc),
        subject=f"Order confirmation - {subject_item}",
        message=plain_text_to_email_html(message),
        now=True,
        reference_doctype="Sales Invoice",
        reference_name=invoice.name,
    )


def _fulfil_checkout_session(session):
    stripe_session_id = session.get("id")

    if not stripe_session_id:
        return

    metadata = session.get("metadata") or {}
    checkout_name = metadata.get("checkout")

    if not checkout_name or not frappe.db.exists("Webshop Checkout", checkout_name):
        frappe.log_error(
            f"Stripe checkout.session.completed missing/unknown checkout doc: {session}",
            "Webshop Purchase Fulfilment Failed",
        )
        return

    checkout = frappe.get_doc("Webshop Checkout", checkout_name)

    # Stripe retries a webhook delivery until it gets a 200 back, so the
    # same completed session can arrive more than once - this is what
    # keeps a retry from double-invoicing/double-unlocking the same
    # already-fulfilled cart.
    if checkout.status == "Paid":
        return

    if not checkout.items:
        frappe.log_error(f"Webshop Checkout {checkout_name} has no items", "Webshop Purchase Fulfilment Failed")
        return

    email = checkout.email
    coach = checkout.coach or ""
    settings = get_settings()

    online_client_name = _get_or_create_online_client(
        full_name=checkout.full_name,
        email=email,
        phone=checkout.phone,
        address_line1=checkout.address_line1,
        address_line2=checkout.address_line2,
        city=checkout.city,
        postcode=checkout.postcode,
        country=checkout.country,
        coach=coach,
    )
    online_client = frappe.get_doc(ONLINE_CLIENT_DOCTYPE, online_client_name)

    add_to_email_group(online_client.email, WEBSHOP_CUSTOMERS_EMAIL_GROUP, full_name=online_client.full_name)

    customer_name = _get_or_create_customer_for_contact(
        online_client.email, online_client.full_name, online_client.get("phone")
    )

    contact_name = frappe.db.get_value("Contact Email", {"email_id": email}, "parent")

    client_name, is_new_client = _get_or_create_portal_client(
        full_name=online_client.full_name, email=email, phone=online_client.get("phone") or "",
    )
    granted_new_portal_access = _ensure_portal_access(client_name, contact_name, email)

    if granted_new_portal_access:
        _ensure_portal_login(email, online_client.full_name)

    invoice = frappe.new_doc("Sales Invoice")
    invoice.customer = customer_name
    invoice.company = settings.company
    invoice.posting_date = nowdate()
    invoice.due_date = nowdate()

    if invoice.meta.has_field("custom_online_client"):
        invoice.custom_online_client = online_client_name
    if invoice.meta.has_field("custom_client"):
        invoice.custom_client = client_name
    if invoice.meta.has_field("custom_stripe_session_id"):
        invoice.custom_stripe_session_id = stripe_session_id

    item_codes = []
    price_list = None

    for line in checkout.items:
        item_codes.append(line.item_code)

        if price_list is None:
            price_list = _default_price_list_for_item(line.item_code, settings.company)

        invoice.append("items", {
            "item_code": line.item_code,
            "item_name": line.item_name,
            "qty": line.qty,
            "rate": line.rate,
        })

    if price_list:
        invoice.selling_price_list = price_list

    if checkout.get("discount_amount"):
        invoice.apply_discount_on = "Grand Total"
        invoice.discount_amount = checkout.discount_amount

    if hasattr(invoice, "set_missing_values"):
        invoice.set_missing_values()
    if hasattr(invoice, "calculate_taxes_and_totals"):
        invoice.calculate_taxes_and_totals()

    invoice.insert(ignore_permissions=True)
    invoice.submit()

    paid_to_account = _get_bank_account_gl_account(settings.bank_account)

    payment_utils.build_and_submit_payment_entry(
        invoice_name=invoice.name,
        paid_to_account=paid_to_account,
        payment_date=nowdate(),
        remarks=f"Stripe payment for online order {invoice.name} (session {stripe_session_id})",
        final_amount=invoice.grand_total,
        reference_no=stripe_session_id,
    )

    unlocked_courses = _unlock_courses_for_purchase(email, item_codes)

    checkout.status = "Paid"
    if checkout.meta.has_field("invoice"):
        checkout.invoice = invoice.name
    checkout.save(ignore_permissions=True)

    if checkout.get("coupon_code"):
        try:
            record_coupon_use(checkout.coupon_code)
        except Exception:
            # The discount itself was already honoured via Stripe -
            # a failure to bump the usage counter shouldn't undo an
            # already-paid order.
            frappe.log_error(frappe.get_traceback(), f"Could not record coupon use - {checkout.name}")

    frappe.db.commit()

    invoice.reload()

    digital_files = []

    if frappe.get_meta("Item").has_field("custom_digital_file"):
        for line in checkout.items:
            file_url = frappe.db.get_value("Item", line.item_code, "custom_digital_file")
            if file_url:
                digital_files.append({"item_name": line.item_name, "url": file_url})

    try:
        _send_order_confirmation_emails(
            invoice, online_client, checkout.items, settings, coach,
            digital_files=digital_files,
            granted_new_portal_access=granted_new_portal_access,
            unlocked_courses=unlocked_courses,
            coupon_code=checkout.get("coupon_code"),
            discount_amount=checkout.get("discount_amount") or 0,
        )
    except Exception:
        # The order itself is already paid and recorded - a failed email
        # shouldn't look like a failed purchase to Stripe (which would
        # otherwise keep retrying the whole webhook, re-running everything
        # above against the now-idempotency-guarded checkout/invoice for
        # nothing).
        frappe.log_error(frappe.get_traceback(), f"Order Confirmation Email Failed - {invoice.name}")


@frappe.whitelist(allow_guest=True, methods=["POST"])
def stripe_webhook():
    settings = get_settings()
    webhook_secret = settings.get_password("stripe_webhook_secret", raise_exception=False)

    if not webhook_secret:
        frappe.local.response.http_status_code = 400
        return {"ok": False}

    import stripe

    payload = frappe.request.get_data(as_text=True)
    sig_header = frappe.get_request_header("Stripe-Signature")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except (ValueError, stripe.error.SignatureVerificationError):
        frappe.local.response.http_status_code = 400
        return {"ok": False}

    if event.get("type") == "checkout.session.completed":
        _fulfil_checkout_session(event["data"]["object"])

    return {"ok": True}
