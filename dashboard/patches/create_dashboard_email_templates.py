"""
Seeds the Email Template records used by email_templates.render_email(), so
they show up in the desk (Email Template list) ready to edit.

Self-healing: creates each one if it's missing, and also backfills it if it
already exists but has no subject/body (which is what an earlier version of
this patch produced on some sites - it guessed the body fieldname was
always "response", which isn't true on every Frappe version). Never
touches a record that already has real content, so a coach's own edits are
never overwritten.
"""

import frappe

from dashboard.api.shared.email_templates import (
    BOOKING_CONFIRMATION_TEMPLATE,
    INTAKE_INVITE_TEMPLATE,
    INVOICE_EMAIL_TEMPLATE,
)

# Tried in this order - whichever of these actually exists as a real field
# on this site's Email Template doctype gets the body content. Different
# Frappe versions have used different names for this field.
BODY_FIELD_CANDIDATES = ["response", "response_html", "message", "content"]

TEMPLATES = [
    {
        # Plain text (not HTML) - none of these three use the desk's HTML
        # editor. plain_text_to_email_html() wraps this into <p> tags per
        # line at send time.
        "name": BOOKING_CONFIRMATION_TEMPLATE,
        "subject": "Your {{ appointment_type }} is confirmed",
        "body": (
            "Hi {{ contact_name }},\n"
            "\n"
            "Your {{ appointment_type }} with {{ coach_name }} is confirmed:\n"
            "\n"
            "{{ date }} at {{ time }}"
            "{% if location_address %}\n"
            "Location: {{ location_address }}{% endif %}\n"
            "\n"
            "We'll be in touch if anything changes. See you then!"
        ),
    },
    {
        "name": INTAKE_INVITE_TEMPLATE,
        "subject": "Your Resilient Kid intake form",
        "body": (
            "Hi {{ contact_name }},\n"
            "\n"
            "Thanks for speaking with us. Please complete the short form below "
            "so we can get {{ client_name }} set up:\n"
            "\n"
            "{{ intake_url }}"
        ),
    },
    {
        "name": INVOICE_EMAIL_TEMPLATE,
        "subject": "Invoice {{ invoice_number }}",
        "body": (
            "Hi {{ customer_name }},\n"
            "\n"
            "I hope you're doing well.\n"
            "\n"
            "Please find attached your invoice.\n"
            "\n"
            "Invoice number: {{ invoice_number }}\n"
            "Amount due: £{{ amount_due }}\n"
            "Payment due by: {{ due_date }}\n"
            "\n"
            "Payment details:\n"
            "{{ bank_details }}\n"
            "\n"
            "Warm regards,\n"
            "{{ coach_name }}\n"
            "{{ company_label }}"
            "{% if coach_email %}\n\n{{ coach_email }}{% endif %}"
            "{% if coach_phone %}\n{{ coach_phone }}{% endif %}"
        ),
    },
]


def _body_fieldname(meta):
    for fieldname in BODY_FIELD_CANDIDATES:
        if meta.has_field(fieldname):
            return fieldname
    return None


def _is_blank(value):
    return not (value or "").strip()


def execute():
    if not frappe.db.exists("DocType", "Email Template"):
        return

    meta = frappe.get_meta("Email Template")
    body_fieldname = _body_fieldname(meta)

    if not body_fieldname:
        frappe.log_error(
            f"Email Template has none of the expected body fields {BODY_FIELD_CANDIDATES}. "
            f"Actual fields: {[f.fieldname for f in meta.fields]}",
            "Create Dashboard Email Templates - No Body Field Found",
        )
        return

    for tpl in TEMPLATES:
        try:
            if frappe.db.exists("Email Template", tpl["name"]):
                doc = frappe.get_doc("Email Template", tpl["name"])

                if not _is_blank(doc.get("subject")) or not _is_blank(doc.get(body_fieldname)):
                    # Already has real content - either seeded correctly
                    # before, or a coach has since edited it. Leave it alone.
                    continue

                if meta.has_field("subject"):
                    doc.subject = tpl["subject"]

                doc.set(body_fieldname, tpl["body"])
                doc.save(ignore_permissions=True)
                continue

            doc = frappe.new_doc("Email Template")
            doc.name = tpl["name"]

            if meta.has_field("subject"):
                doc.subject = tpl["subject"]

            doc.set(body_fieldname, tpl["body"])
            doc.insert(ignore_permissions=True)
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Create Dashboard Email Template Failed: {tpl['name']}")

    frappe.db.commit()
