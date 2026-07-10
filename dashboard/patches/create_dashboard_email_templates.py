"""
Seeds the Email Template records used by email_templates.render_email(), so
they show up in the desk (Email Template list) ready to edit. Only creates
each one if it doesn't already exist, so re-running this (or a coach's own
later edits) is never overwritten.
"""

import frappe

from dashboard.api.shared.email_templates import (
    BOOKING_CONFIRMATION_TEMPLATE,
    INTAKE_INVITE_TEMPLATE,
    INVOICE_EMAIL_TEMPLATE,
)

TEMPLATES = [
    {
        "name": BOOKING_CONFIRMATION_TEMPLATE,
        "subject": "Your {{ appointment_type }} is confirmed",
        "response": (
            "<p>Hi {{ contact_name }},</p>"
            "<p>Your {{ appointment_type }} with {{ coach_name }} is confirmed:</p>"
            "<p><strong>{{ date }} at {{ time }}</strong></p>"
            "{% if location_address %}<p>Location: {{ location_address }}</p>{% endif %}"
            "<p>We'll be in touch if anything changes. See you then!</p>"
        ),
    },
    {
        "name": INTAKE_INVITE_TEMPLATE,
        "subject": "Your Resilient Kid intake form",
        "response": (
            "<p>Hi {{ contact_name }},</p>"
            "<p>Thanks for speaking with us. Please complete the short form below "
            "so we can get {{ client_name }} set up:</p>"
            "<p><a href=\"{{ intake_url }}\">{{ intake_url }}</a></p>"
        ),
    },
    {
        # Plain text (not HTML) - this one populates a plain <textarea> the
        # coach can freely edit before sending, and gets wrapped into <p>
        # tags per line by send_invoice_email() at send time. Keep this as
        # plain lines rather than <p>/<br> markup so that round-trip still
        # works cleanly if it's ever edited back in the desk.
        "name": INVOICE_EMAIL_TEMPLATE,
        "subject": "Invoice {{ invoice_number }}",
        "response": (
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


def execute():
    if not frappe.db.exists("DocType", "Email Template"):
        return

    for tpl in TEMPLATES:
        if frappe.db.exists("Email Template", tpl["name"]):
            continue

        try:
            doc = frappe.new_doc("Email Template")
            doc.name = tpl["name"]

            if doc.meta.has_field("subject"):
                doc.subject = tpl["subject"]

            if doc.meta.has_field("response"):
                doc.response = tpl["response"]

            if doc.meta.has_field("use_html"):
                doc.use_html = 1

            doc.insert(ignore_permissions=True)
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Create Dashboard Email Template Failed: {tpl['name']}")

    frappe.db.commit()
