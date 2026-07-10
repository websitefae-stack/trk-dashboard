"""
Thin wrapper around Frappe's own Email Template doctype so wording for the
system's outgoing emails (booking confirmations, intake form invites) can
be edited from the desk (Email Template list) without a code change.
Falls back to the given hardcoded subject/message if the named template
doesn't exist yet, or Email Template isn't a real doctype on this site.
"""

import re
from html import unescape as _html_unescape

import frappe

BOOKING_CONFIRMATION_TEMPLATE = "Booking Confirmation - Resilient Kid"
INTAKE_INVITE_TEMPLATE = "Client Intake Form Invite - Resilient Kid"
INVOICE_EMAIL_TEMPLATE = "Invoice Email - Resilient Kid"

# Tried in this order - whichever of these is a real field on this site's
# Email Template doctype holds the body content. Different Frappe versions
# have used different names for this field (see the seeding patch,
# patches/create_dashboard_email_templates.py).
BODY_FIELD_CANDIDATES = ["response", "response_html", "message", "content"]

_HTML_TAG_RE = re.compile(r"<[a-zA-Z/][^>]*>")


def _body_fieldname(doc):
    for fieldname in BODY_FIELD_CANDIDATES:
        if doc.meta.has_field(fieldname):
            return fieldname
    return None


def _looks_like_html(text):
    return bool(_HTML_TAG_RE.search(text or ""))


def _html_to_plain_text(html):
    """
    Some sites' Email Template body field is a rich-text (Quill) editor
    rather than plain text, so editing a template there produces real
    markup (e.g. `<div class="ql-editor read-mode"><p>Hi ...`) - that must
    never reach a plain compose <textarea> as visible tag soup. Converts
    block-level breaks to newlines, strips remaining tags, and collapses
    to at most one blank line between paragraphs.
    """
    text = html or ""
    text = re.sub(r"(?is)<br\s*/?>", "\n", text)
    text = re.sub(r"(?is)</p\s*>", "\n\n", text)
    text = re.sub(r"(?is)</div\s*>", "\n", text)
    text = re.sub(r"(?is)<[^>]+>", "", text)
    text = _html_unescape(text)

    lines = [line.strip() for line in text.split("\n")]
    cleaned = []
    blank_run = 0

    for line in lines:
        if not line:
            blank_run += 1
            if blank_run <= 1:
                cleaned.append("")
        else:
            blank_run = 0
            cleaned.append(line)

    return "\n".join(cleaned).strip("\n")


def render_email(template_name, context, fallback_subject, fallback_message):
    """
    The dashboard's own emails are written and edited as plain text (see
    plain_text_to_email_html()) - callers that actually send mail should
    run the result through that before handing it to frappe.sendmail() so
    line breaks show up correctly. Callers that just need to pre-fill an
    editable plain-text textarea (e.g. the invoice/client compose modals)
    should use the raw result as-is; it's already guaranteed plain text
    even if the underlying Email Template itself is HTML (a Quill/rich
    editor field on some sites) - see _html_to_plain_text().
    """
    if template_name and frappe.db.exists("Email Template", template_name):
        try:
            doc = frappe.get_doc("Email Template", template_name)
            body_fieldname = _body_fieldname(doc)
            body = doc.get(body_fieldname) if body_fieldname else None

            if (doc.get("subject") or "").strip() or (body or "").strip():
                subject = frappe.render_template(doc.get("subject") or fallback_subject, context)
                message = frappe.render_template(body or fallback_message, context)

                if _looks_like_html(subject):
                    subject = _html_to_plain_text(subject)

                if _looks_like_html(message):
                    message = _html_to_plain_text(message)

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
