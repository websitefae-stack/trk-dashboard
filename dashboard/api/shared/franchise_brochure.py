"""
Franchise Brochure request handling - the lightest-touch step in the
franchise pipeline (see leads.py for the full Stage 1 process a
prospect eventually moves into). Deliberately does NOT create a Client
Lead itself - see create_franchise_brochure_request_form.py's own
docstring on why; that only happens once they book a Franchisee Call
(public_booking.py) or complete the Information Sheet
(franchise_info_sheet.py).

send_brochure_link (Franchise Brochure Request's own after_insert
hook, see hooks.py) generates the one-time access token and emails the
gated brochure link immediately. Everything AFTER that - the nurture
follow-up emails - is handled generically by the Email Sequence engine
(see email_sequences.py), triggered off this same doctype via an Email
Sequence record Ashley manages entirely in Desk.
"""

import frappe

from dashboard.api.shared.email_templates import (
    render_email,
    plain_text_to_email_html,
    wrap_branded_email_html,
    _looks_like_html,
    FRANCHISE_BROCHURE_LINK_TEMPLATE,
)
from dashboard.api.shared.profile import PUBLIC_SITE_URL
from dashboard.api.shared.mail_throttle import send_email

BROCHURE_PAGE_PATH = "/franchise-brochure"


def send_brochure_link(doc, method=None):
    try:
        _send_brochure_link(doc)
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Franchise Brochure Link Send Failed - {doc.name}")


def _send_brochure_link(doc):
    email = (doc.get("email") or "").strip()

    if not email:
        return

    # Generated once, read_only on the doctype itself - a request can
    # never be re-sent a different link for the same submission (not
    # that anything currently lets a Franchise Brochure Request be
    # edited at all).
    token = frappe.generate_hash(length=32)
    frappe.db.set_value(doc.doctype, doc.name, "token", token)
    frappe.db.commit()

    brochure_url = f"{PUBLIC_SITE_URL}{BROCHURE_PAGE_PATH}?token={token}"

    subject, message = render_email(
        FRANCHISE_BROCHURE_LINK_TEMPLATE,
        {
            "full_name": doc.get("full_name") or "",
            "brochure_url": brochure_url,
            "booking_url": PUBLIC_SITE_URL + "/book-franchise-call",
        },
        fallback_subject="Your Resilient Kid franchise brochure",
        fallback_message=(
            f"Hi {doc.get('full_name') or ''},\n"
            "\n"
            "Thanks for your interest in The Resilient Kid franchise! Here's your link "
            "to the brochure:\n"
            "\n"
            f"{brochure_url}\n"
            "\n"
            "Warm regards,\n"
            "Ashley"
        ),
        strip_html_message=False,
    )

    # A fully custom HTML template (its own layout/branding/buttons) is
    # sent exactly as authored - wrap_branded_email_html would add a
    # SECOND logo header/footer on top of whatever's already built into
    # it. Only the plain-text fallback above goes through the usual
    # flatten-and-rebrand pipeline.
    if _looks_like_html(message):
        final_message = message
    else:
        final_message = wrap_branded_email_html(plain_text_to_email_html(message))

    send_email(
        recipients=[email],
        subject=subject,
        message=final_message,
        reference_doctype=doc.doctype,
        reference_name=doc.name,
    )
