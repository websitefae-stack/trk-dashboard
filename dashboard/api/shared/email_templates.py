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

from dashboard.api.shared.profile import PUBLIC_SITE_URL, OFFICE_USER

HUB_LOGO_URL = PUBLIC_SITE_URL + "/files/TRHub_Logo.jpg"

# The brand's four wordmark logos, shown in a row as the default email
# footer - same files already used for this in the site's web form CSS
# (.web-form-container::after).
BRAND_WORDMARK_URLS = [
    (PUBLIC_SITE_URL + "/files/TRKid_Wordmark_Logo.png", "The Resilient Kid"),
    (PUBLIC_SITE_URL + "/files/TRTeen_Wordmark_Logo.png", "The Resilient Teen"),
    (PUBLIC_SITE_URL + "/files/TRPeople_Wordmark_Logo.png", "The Resilient People"),
    (PUBLIC_SITE_URL + "/files/TRSchool_Wordmark_Logo.png", "The Resilient School"),
]

BOOKING_CONFIRMATION_TEMPLATE = "Booking Confirmation - Resilient Kid"
INTAKE_INVITE_TEMPLATE = "Client Intake Form Invite - Resilient Kid"
PODCAST_INVITE_TEMPLATE = "Podcast Guest Form Invite - Resilient Kid"
INVOICE_EMAIL_TEMPLATE = "Invoice Email - Resilient Kid"
FRANCHISE_BROCHURE_LINK_TEMPLATE = "Franchise Brochure Link - Resilient Kid"

# Tried in this order - whichever of these is a real field on this site's
# Email Template doctype holds the body content. Different Frappe versions
# have used different names for this field (see the seeding patch,
# patches/create_dashboard_email_templates.py).
BODY_FIELD_CANDIDATES = ["response", "response_html", "message", "content"]

_HTML_TAG_RE = re.compile(r"<[a-zA-Z/][^>]*>")


def _body_fieldname(doc):
    """
    Among the candidates that exist on this doctype, prefers whichever
    one actually HAS content over just the first one that merely exists
    in the list - this is the fix for a real bug: a site can have more
    than one of these fields present (an old/unused one alongside
    the one Desk's form actually edits today), and picking by bare
    existence alone can silently read a stale/blank field forever while
    completely ignoring real, current content sitting in a later
    candidate. Only falls back to "first one that exists" when none of
    them have content, which preserves the original behaviour for a
    genuinely blank template.
    """
    existing = [f for f in BODY_FIELD_CANDIDATES if doc.meta.has_field(f)]

    for fieldname in existing:
        if (doc.get(fieldname) or "").strip():
            return fieldname

    return existing[0] if existing else None


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


def render_email(template_name, context, fallback_subject, fallback_message, strip_html_message=True):
    """
    The dashboard's own emails are mostly written and edited as plain
    text (see plain_text_to_email_html()) - callers that actually send
    mail should run the result through that before handing it to
    frappe.sendmail() so line breaks show up correctly. Callers that
    just need to pre-fill an editable plain-text textarea (e.g. the
    invoice/client compose modals) should use the raw result as-is;
    it's already guaranteed plain text even if the underlying Email
    Template itself is HTML (a Quill/rich editor field on some sites) -
    see _html_to_plain_text().

    strip_html_message=False is for the other kind of template this app
    now also supports: a fully custom-designed HTML email (branded
    buttons, images, its own layout) someone deliberately wrote, meant
    to be sent exactly as authored - stripping that down to plain text
    first (the default behaviour, built for the Quill-artifact case
    above) would silently throw away every bit of that design. Pass
    this when the caller is actually sending mail with a template that
    might be real HTML, never for a caller that's pre-filling a plain
    editable textarea (stripping is still correct there). The subject
    is always stripped to plain text regardless - a subject line should
    never contain markup either way.
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

                if strip_html_message and _looks_like_html(message):
                    message = _html_to_plain_text(message)

                return subject, message
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Render Email Template Failed: {template_name}")

    return (
        frappe.render_template(fallback_subject, context),
        frappe.render_template(fallback_message, context),
    )


# Every merge field used by ANY Email Template seeded across this app -
# see the various render_email(...) call sites (calendar.py, leads.py,
# invoices.py, public_booking.py, school_pipeline.py, email_sequences.py,
# franchise_brochure.py). Kept in one place so send_test_email() below
# can render any template with a believable preview regardless of which
# merge fields it actually uses - Jinja silently renders an unknown one
# as blank rather than erroring, so listing fields a given template
# doesn't use is harmless.
SAMPLE_MERGE_CONTEXT = {
    "recipient_name": "Alex Example",
    "recipient_email": "alex@example.com",
    "full_name": "Alex Example",
    "contact_name": "Alex Example",
    "client_name": "Jamie Example",
    "school_name": "Example Primary School",
    "appointment_type": "Franchisee Call",
    "coach_name": "Ashley",
    "invoice_number": "SINV-TEST-0001",
    "company_label": "The Resilient Kid",
    # A real brochure_url always carries a genuine, single-use token (see
    # franchise_brochure.py) that /franchise-brochure checks against a
    # real Franchise Brochure Request record - a made-up sample token
    # would correctly get bounced to the request form, same as any
    # other invalid/guessed link, which isn't useful for previewing
    # what the email itself looks like. Points at the plain /brochure
    # page instead (no token, nothing to fake) purely for this preview.
    "brochure_url": PUBLIC_SITE_URL + "/brochure",
    "booking_url": PUBLIC_SITE_URL + "/book-franchise-call",
}


@frappe.whitelist()
def debug_email_template(template_name=None):
    """TEMPORARY diagnostic - not called from the frontend. Visit
    /api/method/dashboard.api.shared.email_templates.debug_email_
    template?template_name=<name> while logged in as office to see
    exactly which field _body_fieldname() picks for a given template,
    and the raw value sitting in every BODY_FIELD_CANDIDATES field - so
    editing one field in Desk while this reads a different, stale one
    is visible directly rather than guessed at. Remove once the real
    bug is found."""
    if frappe.session.user != OFFICE_USER:
        frappe.throw(frappe._("You are not allowed to access this page."), frappe.PermissionError)

    template_name = (template_name or "").strip()
    if not template_name or not frappe.db.exists("Email Template", template_name):
        frappe.throw(frappe._("Give a real Email Template name."))

    doc = frappe.get_doc("Email Template", template_name)
    detected_fieldname = _body_fieldname(doc)

    candidate_values = {}
    for fieldname in BODY_FIELD_CANDIDATES:
        if doc.meta.has_field(fieldname):
            value = doc.get(fieldname)
            candidate_values[fieldname] = (value or "")[:500]
        else:
            candidate_values[fieldname] = "(field does not exist on this doctype)"

    return {
        "template_name": template_name,
        "modified": str(doc.modified),
        "subject": doc.get("subject"),
        "detected_body_fieldname": detected_fieldname,
        "detected_body_value": (doc.get(detected_fieldname) or "")[:500] if detected_fieldname else None,
        "all_candidate_fields_on_doctype": [f.fieldname for f in doc.meta.fields if "response" in f.fieldname.lower() or "content" in f.fieldname.lower() or "message" in f.fieldname.lower() or "html" in f.fieldname.lower()],
        "candidate_values": candidate_values,
    }


@frappe.whitelist()
def send_test_email(template_name=None, test_email=None):
    """
    Office-only (not Ashley's own login - see /franchisor_db/email_
    templates's own nav link and get_context, which match this same
    restriction) - lets office see exactly what an Email Template will
    actually look like, sent to a real inbox, before it ever goes out for
    real. Renders with SAMPLE_MERGE_CONTEXT above rather than any real
    document, so this works for every template the same way regardless
    of what normally triggers it; any merge field a given template
    doesn't use just doesn't appear, same as a real send.
    """
    from dashboard.api.shared.permissions import ensure_logged_in
    from dashboard.api.shared.mail_throttle import send_email

    ensure_logged_in()
    # Literal check, not ensure_office_user()/is_franchisor_user() -
    # those both treat Ashley and office as the same tier.
    if frappe.session.user != OFFICE_USER:
        frappe.throw(frappe._("You are not allowed to access this page."), frappe.PermissionError)

    template_name = (template_name or "").strip()
    if not template_name or not frappe.db.exists("Email Template", template_name):
        frappe.throw(frappe._("Choose a template to test."))

    test_email = (test_email or "").strip() or frappe.session.user
    if not test_email or test_email == "Guest":
        frappe.throw(frappe._("Enter an email address to send the test to."))

    subject, message = render_email(
        template_name,
        SAMPLE_MERGE_CONTEXT,
        fallback_subject="(This template has no subject/body set yet)",
        fallback_message="(This template has no subject/body set yet)",
        strip_html_message=False,
    )

    # A fully custom HTML template (its own layout/branding/buttons -
    # e.g. the franchise brochure link email) is sent exactly as
    # authored - wrapping it in wrap_branded_email_html would add a
    # SECOND logo header/footer on top of whatever branding is already
    # built into it. Only a genuinely plain-text template goes through
    # the usual flatten-and-rebrand pipeline.
    if _looks_like_html(message):
        final_message = message
    else:
        final_message = wrap_branded_email_html(plain_text_to_email_html(message))

    send_email(
        recipients=[test_email],
        subject=f"[TEST] {subject}",
        message=final_message,
    )

    return {"ok": 1, "sent_to": test_email}


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


@frappe.whitelist()
def list_email_templates():
    """For the /franchisor_db/email_templates page (office-only, not
    Ashley's own login) - every Email Template on the site plus whether
    it actually has a subject/body set yet, so office can see at a
    glance which of the 12+ templates still need writing."""
    from dashboard.api.shared.permissions import ensure_logged_in

    ensure_logged_in()
    if frappe.session.user != OFFICE_USER:
        frappe.throw(frappe._("You are not allowed to access this page."), frappe.PermissionError)

    if not frappe.db.exists("DocType", "Email Template"):
        return []

    meta = frappe.get_meta("Email Template")
    body_fieldname = None
    for fieldname in BODY_FIELD_CANDIDATES:
        if meta.has_field(fieldname):
            body_fieldname = fieldname
            break

    fields = ["name", "subject"]
    if body_fieldname and body_fieldname not in fields:
        fields.append(body_fieldname)

    rows = frappe.get_all("Email Template", fields=fields, order_by="name asc", limit_page_length=200)

    result = []
    for row in rows:
        body = row.get(body_fieldname) if body_fieldname else None
        result.append({
            "name": row.get("name"),
            "has_content": bool((row.get("subject") or "").strip() or (body or "").strip()),
        })
    return result


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


# A logo/table cell per brand wordmark - height is set as both an HTML
# attribute and inline CSS, since Outlook desktop (the Word rendering
# engine) only honours the HTML attribute on <img>, not CSS, and
# ignoring that is exactly what made the header logo render at its full
# native size instead of a sensible thumbnail. Width deliberately left
# unset (as both an attribute and in CSS) - these are wordmarks, not
# square icons, so a fixed width squashed/stretched them; with only
# height constrained, every client (Outlook included) scales width to
# match each logo's own aspect ratio automatically - same fix already
# applied to the course-access email's own brand logo row (course_
# unlock_on_payment.py's _email_brand_logo_row).
_WORDMARK_CELLS_HTML = "".join(
    f'<td align="center" style="padding:4px 8px;">'
    f'<img src="{url}" alt="{alt}" height="80" style="display:block; height:80px; border:0;">'
    f"</td>"
    for url, alt in BRAND_WORDMARK_URLS
)

DEFAULT_EMAIL_FOOTER_HTML = f"""
<table role="presentation" align="center" cellpadding="0" cellspacing="0" style="margin:0 auto;">
  <tr>{_WORDMARK_CELLS_HTML}</tr>
</table>
"""


def wrap_branded_email_html(body_html, logo_url=None, footer_html=None):
    """
    Wraps an already-built message body (e.g. the output of
    plain_text_to_email_html()) in a simple branded shell - a logo at the
    top, the message in the middle, the four brand wordmark logos at the
    bottom - so an outgoing email reads as coming from the business
    rather than a bare paragraph of text. logo_url defaults to the stock
    Resilient Hub logo, but a caller with its own configurable branding
    (see School Pipeline's School Pipeline Branding settings) can
    override it. footer_html, if given, is extra text shown above the
    wordmark row (e.g. a custom footer message) - the wordmark row itself
    always shows, since that's the standing brand footer.

    Built as a <table> throughout rather than <div>/CSS, and every image
    carries an explicit HTML width attribute - both deliberate for
    Outlook desktop, which renders HTML email through Word's engine and
    is unreliable with plain CSS layout and outright ignores CSS
    max-width on images.
    """
    body_html = body_html or ""
    logo_url = logo_url or HUB_LOGO_URL
    footer_html = footer_html or ""

    return f"""
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px; margin:0 auto; font-family:Arial, Helvetica, sans-serif; color:#222222;">
      <tr>
        <td style="text-align:center; padding:24px 0;">
          <img src="{logo_url}" alt="" width="180" style="display:inline-block; width:180px; max-width:180px; height:auto; border:0;">
        </td>
      </tr>
      <tr>
        <td style="padding:0 24px 24px; font-size:15px; line-height:1.6;">
          {body_html}
        </td>
      </tr>
      <tr>
        <td style="border-top:1px solid #e0e0e0; padding:18px 24px; text-align:center; font-size:12px; color:#888888;">
          {footer_html}
          {DEFAULT_EMAIL_FOOTER_HTML}
        </td>
      </tr>
    </table>
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
