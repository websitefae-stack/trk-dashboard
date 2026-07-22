"""
Bridges the webshop app's "Contact Us" enquiry flow into this app's own
Client Lead board (the one Ashley/office actually use day to day - see
leads.py), and notifies them when it happens.

webshop's create_lead_for_item_inquiry() (apps/webshop/webshop/webshop/
shopping_cart/cart.py) creates a plain core Frappe "Lead" with source
"Product Inquiry", then adds the enquiry's subject/message as a Comment on
it afterwards - two separate steps in the same request, which is why this
needs two hooks (see hooks.py) rather than one: the Comment doesn't exist
yet at the point the Lead itself is inserted.

Both hooks are wrapped defensively - webshop's flow is public-facing
(allow_guest), so a problem here must never surface as an error to a
website visitor filling in the contact form. Anything unexpected is
logged, never raised.
"""

import re

import frappe

from dashboard.api.shared.notifications import create_trk_notification

WEBSHOP_LEAD_SOURCE = "Product Inquiry"
CLIENT_LEAD_NOTIFY_USERS = ["ashley@theresilientkid.co.uk", "office@theresilienthub.co.uk"]


def sync_webshop_lead(doc, method=None):
    if doc.get("source") != WEBSHOP_LEAD_SOURCE:
        return

    if not frappe.db.exists("DocType", "Client Lead"):
        return

    try:
        _create_client_lead_from_webshop(doc)
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Webshop Lead Sync - {doc.name}")


def _create_client_lead_from_webshop(lead_doc):
    # client_name/contact_name are both mandatory on Client Lead - a
    # webshop product enquiry doesn't know "the young person's name" at
    # all, so this reuses whatever real contact was actually given rather
    # than leaving a required field blank.
    contact_name = lead_doc.get("lead_name") or "Website Enquiry"
    client_name = lead_doc.get("company_name") or contact_name

    client_lead = frappe.new_doc("Client Lead")
    client_lead.status = "New"
    client_lead.source = "Website Enquiry"
    client_lead.source_lead = lead_doc.name
    client_lead.contact_name = contact_name
    client_lead.contact_email = lead_doc.get("email_id")
    client_lead.contact_mobile = lead_doc.get("phone")
    client_lead.client_name = client_name
    client_lead.enquiry_reason = (
        "New website enquiry - message not loaded yet, refresh in a moment "
        "(or open the linked Website Lead)."
    )
    client_lead.insert(ignore_permissions=True)

    for recipient in CLIENT_LEAD_NOTIFY_USERS:
        try:
            create_trk_notification(
                recipient_user=recipient,
                notification_type="Task",
                message=(
                    f"New website enquiry from {contact_name}"
                    + (f" ({client_lead.contact_email})" if client_lead.contact_email else "")
                    + " - see the Client Lead for details."
                ),
                priority="High",
                reference_doctype="Client Lead",
                reference_name=client_lead.name,
            )
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Webshop Lead Notify - {client_lead.name} - {recipient}")


def sync_webshop_lead_comment(doc, method=None):
    if doc.get("reference_doctype") != "Lead" or not doc.get("reference_name"):
        return

    try:
        _apply_comment_to_client_lead(doc)
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Webshop Lead Comment Sync - {doc.name}")


def _apply_comment_to_client_lead(comment_doc):
    if not frappe.db.exists("DocType", "Client Lead"):
        return

    client_lead_name = frappe.db.get_value(
        "Client Lead", {"source_lead": comment_doc.reference_name}, "name"
    )
    if not client_lead_name:
        return

    plain_text = re.sub(r"<[^>]+>", " ", comment_doc.get("content") or "").strip()
    plain_text = re.sub(r"\s+", " ", plain_text)
    if not plain_text:
        return

    frappe.db.set_value("Client Lead", client_lead_name, "enquiry_reason", plain_text, update_modified=False)
