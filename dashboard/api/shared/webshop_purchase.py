"""
Guest-facing checkout for one-off online purchases (services, products,
merch) - deliberately separate from both the stock Frappe webshop app
(its checkout hard-requires a login, which is exactly the problem this
replaces) and the coaching Client/invoicing flow in invoices.py, so an
online purchase never mixes into the real Client list (see Online
Client doctype - Ashley links the two manually later, by email).

Mirrors the guest-facing shape already established by public_booking.py:
a no-login Jinja page in resilient_domains, paired with
@frappe.whitelist(allow_guest=True) endpoints here. "Buy Now" only -
browsing/product display stays wherever the item is already shown.

Price is always computed here from the Item's own Item Price, never
trusted from the browser - the client only ever sends an item_code and
a quantity.
"""

import frappe
from frappe import _
from frappe.utils import nowdate, fmt_money, get_url

from dashboard.dashboard.doctype.webshop_payment_settings.webshop_payment_settings import get_settings
from dashboard.api.shared.email_templates import plain_text_to_email_html
from dashboard.api.shared.item_access import _get_coach_login
from dashboard.api.shared.invoices import _get_bank_account_gl_account
from dashboard.api.shared import payment_utils

ONLINE_CLIENT_DOCTYPE = "Online Client"


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

    price_list = item_default.get("default_price_list")
    rate = 0
    currency = "GBP"

    if price_list:
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

    item_doc = frappe.get_doc("Item", item_code)

    return {
        "item_code": item_code,
        "item_name": item_doc.item_name or item_code,
        "description": item_doc.description or "",
        "rate": rate,
        "currency": currency,
        "price_list": price_list,
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
        "rate": item["rate"],
        "currency": item["currency"],
    }


@frappe.whitelist(allow_guest=True)
def create_checkout_session(
    item_code=None,
    qty=1,
    full_name=None,
    email=None,
    phone=None,
    address_line1=None,
    address_line2=None,
    city=None,
    postcode=None,
    country=None,
    coach=None,
    success_url=None,
    cancel_url=None,
):
    settings = get_settings()

    if not settings.enabled:
        frappe.throw(_("Online checkout isn't available right now."))

    stripe_secret_key = settings.get_password("stripe_secret_key", raise_exception=False)

    if not stripe_secret_key:
        frappe.throw(_("Online checkout isn't fully set up yet."))

    item_code = (item_code or "").strip()
    full_name = (full_name or "").strip()
    email = (email or "").strip()
    qty = max(1, int(_to_float(qty) or 1))

    if not full_name:
        frappe.throw(_("Full name is required."))

    if not email:
        frappe.throw(_("Email is required."))

    coach = (coach or "").strip()
    if coach and not frappe.db.exists("Coach", coach):
        coach = ""

    item = _get_purchasable_item(item_code, settings.company)
    unit_amount = int(round(_to_float(item["rate"]) * 100))

    if unit_amount <= 0:
        frappe.throw(_("This item cannot be purchased online right now."))

    import stripe

    stripe.api_key = stripe_secret_key

    checkout_session = stripe.checkout.Session.create(
        mode="payment",
        payment_method_types=["card"],
        customer_email=email,
        line_items=[{
            "price_data": {
                "currency": (item["currency"] or "GBP").lower(),
                "product_data": {"name": item["item_name"]},
                "unit_amount": unit_amount,
            },
            "quantity": qty,
        }],
        # Reconstructed server-side by the webhook once payment actually
        # succeeds - nothing here is trusted, this is only how the details
        # given at checkout survive the redirect to Stripe and back.
        metadata={
            "item_code": item_code,
            "qty": str(qty),
            "full_name": full_name,
            "email": email,
            "phone": phone or "",
            "address_line1": address_line1 or "",
            "address_line2": address_line2 or "",
            "city": city or "",
            "postcode": postcode or "",
            "country": country or "",
            "coach": coach or "",
        },
        success_url=success_url or (get_url() + "/order-confirmed?session_id={CHECKOUT_SESSION_ID}"),
        cancel_url=cancel_url or get_url(),
    )

    return {"checkout_url": checkout_session.url}


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


def _get_or_create_customer_for_online_client(online_client):
    existing_contact_name = frappe.db.get_value(
        "Contact Email", {"email_id": online_client.email}, "parent"
    )

    if existing_contact_name:
        contact = frappe.get_doc("Contact", existing_contact_name)
    else:
        first_name, last_name = _split_full_name(online_client.full_name)
        contact = frappe.new_doc("Contact")
        contact.first_name = first_name or online_client.email
        if last_name:
            contact.last_name = last_name
        contact.append("email_ids", {"email_id": online_client.email, "is_primary": 1})
        if online_client.phone:
            contact.append("phone_nos", {"phone": online_client.phone, "is_primary_mobile_no": 1})
        contact.insert(ignore_permissions=True)

    for link in contact.get("links") or []:
        if link.get("link_doctype") == "Customer" and frappe.db.exists("Customer", link.get("link_name")):
            return link.get("link_name")

    customer_doc = frappe.new_doc("Customer")
    customer_doc.customer_type = "Individual"
    customer_doc.customer_name = online_client.full_name or online_client.email
    customer_doc.insert(ignore_permissions=True)

    contact.append("links", {"link_doctype": "Customer", "link_name": customer_doc.name})
    contact.save(ignore_permissions=True)

    return customer_doc.name


def _send_order_confirmation_emails(invoice, online_client, item, qty, settings, coach):
    amount_display = fmt_money(invoice.grand_total, currency=invoice.currency)

    message = (
        f"Hi {online_client.full_name},\n"
        "\n"
        "Thanks for your order - here's your confirmation.\n"
        "\n"
        f"{item.get('item_name')} x{qty} - {amount_display}\n"
        "\n"
        f"Order reference: {invoice.name}\n"
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

    frappe.sendmail(
        recipients=[online_client.email],
        cc=list(cc),
        subject=f"Order confirmation - {item.get('item_name')}",
        message=plain_text_to_email_html(message),
        now=True,
        reference_doctype="Sales Invoice",
        reference_name=invoice.name,
    )


def _fulfil_checkout_session(session):
    stripe_session_id = session.get("id")

    if not stripe_session_id:
        return

    # Stripe retries a webhook delivery until it gets a 200 back, so the
    # same completed session can arrive more than once - this is what
    # keeps a retry from creating a second invoice for the same payment.
    if frappe.db.exists("Sales Invoice", {"custom_stripe_session_id": stripe_session_id}):
        return

    metadata = session.get("metadata") or {}
    item_code = metadata.get("item_code")
    email = metadata.get("email") or (session.get("customer_details") or {}).get("email") or ""

    if not item_code or not email:
        frappe.log_error(
            f"Stripe checkout.session.completed missing item_code/email: {session}",
            "Webshop Purchase Fulfilment Failed",
        )
        return

    qty = max(1, int(_to_float(metadata.get("qty")) or 1))
    coach = metadata.get("coach") or ""

    settings = get_settings()
    item = _get_purchasable_item(item_code, settings.company)

    # The item's current price (re-fetched above) is only used for the
    # item name/description/price list - the amount actually invoiced
    # always comes from what Stripe actually charged (amount_total), not
    # today's price, in case the price changed between checkout starting
    # and this webhook firing.
    charged_total = _to_float(session.get("amount_total")) / 100
    item["rate"] = round(charged_total / qty, 2) if charged_total else item["rate"]

    online_client_name = _get_or_create_online_client(
        full_name=metadata.get("full_name") or "",
        email=email,
        phone=metadata.get("phone") or "",
        address_line1=metadata.get("address_line1") or "",
        address_line2=metadata.get("address_line2") or "",
        city=metadata.get("city") or "",
        postcode=metadata.get("postcode") or "",
        country=metadata.get("country") or "",
        coach=coach,
    )
    online_client = frappe.get_doc(ONLINE_CLIENT_DOCTYPE, online_client_name)

    customer_name = _get_or_create_customer_for_online_client(online_client)

    invoice = frappe.new_doc("Sales Invoice")
    invoice.customer = customer_name
    invoice.company = settings.company
    invoice.posting_date = nowdate()
    invoice.due_date = nowdate()
    invoice.selling_price_list = item.get("price_list")

    if invoice.meta.has_field("custom_online_client"):
        invoice.custom_online_client = online_client_name
    if invoice.meta.has_field("custom_stripe_session_id"):
        invoice.custom_stripe_session_id = stripe_session_id

    invoice.append("items", {
        "item_code": item_code,
        "item_name": item.get("item_name"),
        "description": item.get("description"),
        "qty": qty,
        "rate": item.get("rate"),
    })

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

    frappe.db.commit()

    invoice.reload()

    try:
        _send_order_confirmation_emails(invoice, online_client, item, qty, settings, coach)
    except Exception:
        # The order itself is already paid and recorded - a failed email
        # shouldn't look like a failed purchase to Stripe (which would
        # otherwise keep retrying the whole webhook, re-running everything
        # above against the now-idempotency-guarded invoice for nothing).
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
