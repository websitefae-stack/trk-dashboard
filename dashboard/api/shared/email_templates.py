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

from dashboard.api.shared.profile import PUBLIC_SITE_URL

HUB_LOGO_URL = PUBLIC_SITE_URL + "/files/TRHub_Logo.jpg"

BOOKING_CONFIRMATION_TEMPLATE = "Booking Confirmation - Resilient Kid"
INTAKE_INVITE_TEMPLATE = "Client Intake Form Invite - Resilient Kid"
PODCAST_INVITE_TEMPLATE = "Podcast Guest Form Invite - Resilient Kid"
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


def _default_outgoing_email():
    if not frappe.db.exists("DocType", "Email Account"):
        return ""
    return frappe.db.get_value("Email Account", {"default_outgoing": 1}, "email_id") or ""


@frappe.whitelist()
def get_email_sender_options():
    """
    "From" choices for the compose modals. Deliberately office-only now -
    this used to also offer "My email (coach's own address)", which sent
    through that coach's own individually Google-OAuth-connected Email
    Account. Those tokens expire on their own schedule regardless of
    anything the coach does, and there was no graceful fallback when one
    had - it just failed outright. Every send now always goes through the
    one shared, reliably-configured office account (see every
    frappe.sendmail() call across this app - none of them set `sender`
    anymore); reply_to is what keeps a client's reply landing with the
    coach personally, not this.
    """
    if frappe.session.user == "Guest":
        frappe.throw(frappe._("Login required"), frappe.PermissionError)

    default_email = _default_outgoing_email()
    office_label = f"Office email ({default_email})" if default_email else "Office email (default)"

    return [{"value": "", "label": office_label}]


def parse_email_list(value):
    """Splits a comma/semicolon separated "Cc" field into a clean list."""
    if not value:
        return []
    return [addr.strip() for addr in re.split(r"[,;]", value) if addr.strip()]


def plain_text_to_email_html(message):
    """
    Wraps plain-text lines (real newlines, no markup) into <p> tags for
    sendmail - unless the text already looks like it contains HTML (e.g.
    the School Pipeline's rich text email composer, or someone pasting
    markup straight into the plain Email Template field), in which case
    it's sent through as-is rather than being double-wrapped. Uses the
    same "does this contain a tag at all" check as _looks_like_html()
    rather than only recognising a leading <p>/<div> - the rich text
    composer's output can just as easily start with <h2>, <b> or <a>.
    """
    message = (message or "").strip()

    if _looks_like_html(message):
        return message

    return "<p>" + "</p><p>".join(
        line.strip() for line in message.splitlines() if line.strip()
    ) + "</p>"


DEFAULT_EMAIL_FOOTER_HTML = (
    '<p style="margin:0 0 4px;">The Resilient Hub</p>'
    f'<p style="margin:0;"><a href="{PUBLIC_SITE_URL}" style="color:#888888;">{PUBLIC_SITE_URL.replace("https://", "")}</a></p>'
)


def wrap_branded_email_html(body_html, logo_url=None, footer_html=None):
    """
    Wraps an already-built message body (e.g. the output of
    plain_text_to_email_html()) in a simple branded shell - a logo at the
    top, the message in the middle, a footer at the bottom - so an
    outgoing email reads as coming from the business rather than a bare
    paragraph of text. logo_url/footer_html default to the stock
    Resilient Hub logo/footer, but a caller with its own configurable
    branding (see School Pipeline's School Pipeline Branding settings)
    can override either.
    """
    body_html = body_html or ""
    logo_url = logo_url or HUB_LOGO_URL
    footer_html = footer_html if footer_html is not None else DEFAULT_EMAIL_FOOTER_HTML

    return f"""
    <div style="max-width:600px; margin:0 auto; font-family:Arial, Helvetica, sans-serif; color:#222222;">
      <div style="text-align:center; padding:24px 0;">
        <img src="{logo_url}" alt="" style="max-width:220px; height:auto;">
      </div>
      <div style="padding:0 24px 24px; font-size:15px; line-height:1.6;">
        {body_html}
      </div>
      <div style="border-top:1px solid #e0e0e0; padding:18px 24px; text-align:center; font-size:12px; color:#888888;">
        {footer_html}
      </div>
    </div>
    """


@frappe.whitelist()
def preview_email_html(message=None):
    """
    Lets any compose modal (invoice email, statement, report, generic
    client email) show exactly what plain_text_to_email_html() will
    actually send, before anyone clicks Send - calling the real function
    here rather than approximating it client-side guarantees the preview
    can never drift out of sync with what actually gets emailed.
    """
    return {"html": plain_text_to_email_html(message or "")}
