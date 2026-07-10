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

# Tried in this order - whichever of these is a real field on this site's
# Email Template doctype holds the body content. Different Frappe versions
# have used different names for this field (see the seeding patch,
# patches/create_dashboard_email_templates.py).
BODY_FIELD_CANDIDATES = ["response", "response_html", "message", "content"]


def _body_fieldname(doc):
    for fieldname in BODY_FIELD_CANDIDATES:
        if doc.meta.has_field(fieldname):
            return fieldname
    return None


def render_email(template_name, context, fallback_subject, fallback_message):
    """
    Every dashboard Email Template is written and edited as plain text
    (Ashley's site doesn't offer an HTML editor for these) - callers that
    actually send mail should run the result through
    plain_text_to_email_html() before handing it to frappe.sendmail(), so
    line breaks show up correctly. Callers that just need to pre-fill an
    editable plain-text textarea (e.g. the invoice compose modal) should
    use the raw result as-is.
    """
    if template_name and frappe.db.exists("Email Template", template_name):
        try:
            doc = frappe.get_doc("Email Template", template_name)
            body_fieldname = _body_fieldname(doc)
            body = doc.get(body_fieldname) if body_fieldname else None

            if (doc.get("subject") or "").strip() or (body or "").strip():
                subject = frappe.render_template(doc.get("subject") or fallback_subject, context)
                message = frappe.render_template(body or fallback_message, context)
                return subject, message
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Render Email Template Failed: {template_name}")

    return (
        frappe.render_template(fallback_subject, context),
        frappe.render_template(fallback_message, context),
    )


@frappe.whitelist()
def get_email_template_options():
    """
    Every Email Template on the site, not just the three this app seeds -
    Ashley may have others already set up for different purposes, and
    should be able to pick any of them when composing an email by hand
    (see the "Send Invoice" button on the Client Details page).
    """
    if frappe.session.user == "Guest":
        frappe.throw(frappe._("Login required"), frappe.PermissionError)

    if not frappe.db.exists("DocType", "Email Template"):
        return []

    rows = frappe.get_all("Email Template", fields=["name"], order_by="name asc", limit_page_length=200)
    return [{"value": row.get("name"), "label": row.get("name")} for row in rows]


def plain_text_to_email_html(message):
    """
    Wraps plain-text lines (real newlines, no markup) into <p> tags for
    sendmail - unless the text already looks like it contains block-level
    HTML (e.g. someone pasted markup straight into the plain Email
    Template field), in which case it's sent through as-is rather than
    being double-wrapped.
    """
    message = (message or "").strip()

    if message[:10].lstrip().lower().startswith(("<p", "<div")):
        return message

    return "<p>" + "</p><p>".join(
        line.strip() for line in message.splitlines() if line.strip()
    ) + "</p>"
