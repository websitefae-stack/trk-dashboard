"""
Thin wrapper around Frappe's own Email Template doctype so wording for the
system's outgoing emails (booking confirmations, intake form invites) can
be edited from the desk (Email Template list) without a code change.
Falls back to the given hardcoded subject/message if the named template
doesn't exist yet, or Email Template isn't a real doctype on this site.
"""

import frappe

BOOKING_CONFIRMATION_TEMPLATE = "Booking Confirmation - Resilient Kid"
INTAKE_INVITE_TEMPLATE = "Client Intake Form Invite - Resilient Kid"
INVOICE_EMAIL_TEMPLATE = "Invoice Email - Resilient Kid"


def render_email(template_name, context, fallback_subject, fallback_message):
    if template_name and frappe.db.exists("Email Template", template_name):
        try:
            doc = frappe.get_doc("Email Template", template_name)
            subject = frappe.render_template(doc.subject or fallback_subject, context)
            message = frappe.render_template(doc.response or fallback_message, context)
            return subject, message
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Render Email Template Failed: {template_name}")

    return (
        frappe.render_template(fallback_subject, context),
        frappe.render_template(fallback_message, context),
    )
