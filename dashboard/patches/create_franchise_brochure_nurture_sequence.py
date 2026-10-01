"""
Seeds the starter "Franchise Brochure Nurture" Email Sequence - the
generic engine in email_sequences.py needs one of these to actually send
anything after the immediate brochure-link email (see
franchise_brochure.send_brochure_link), triggered off the same
"Franchise Brochure Request" doctype.

Three placeholder steps/templates only - Ashley has her own sequence
copy already written and just needs to paste it into each Email
Template below (Desk - Email Template list), overwriting the
"REPLACE ME" placeholder text. Every step's template can use
{{ recipient_name }} and {{ booking_url }} (the Franchisee Call booking
link - see email_sequences._send_next_step) as merge fields.

Deliberately created with is_active = 0 on the Email Sequence itself -
flip that to 1 in Desk once the real copy is in, so nobody is enrolled
and sent placeholder text in the meantime. Re-runs safely: an existing
Email Sequence/Email Template is never overwritten past this first
creation (same create-if-missing/update-if-blank-only approach as
create_franchise_brochure_link_email_template.py), so this never
clobbers whatever Ashley has already edited in here.
"""

import frappe

SEQUENCE_NAME = "Franchise Brochure Nurture"
TRIGGER_DOCTYPE = "Franchise Brochure Request"

BODY_FIELD_CANDIDATES = ["response", "response_html", "message", "content"]

STEPS = [
    {
        "step_number": 1,
        "delay_days": 2,
        "template_name": "Franchise Brochure Follow-up 1 - Resilient Kid",
        "subject": "Any questions about The Resilient Kid franchise?",
        "body": (
            "Hi {{ recipient_name }},\n"
            "\n"
            "REPLACE ME - Ashley's own follow-up copy goes here.\n"
            "\n"
            "If you'd like to chat it through, you can book a call with me here:\n"
            "\n"
            "{{ booking_url }}\n"
            "\n"
            "Warm regards,\n"
            "Ashley"
        ),
    },
    {
        "step_number": 2,
        "delay_days": 5,
        "template_name": "Franchise Brochure Follow-up 2 - Resilient Kid",
        "subject": "Thinking about The Resilient Kid franchise?",
        "body": (
            "Hi {{ recipient_name }},\n"
            "\n"
            "REPLACE ME - Ashley's own follow-up copy goes here.\n"
            "\n"
            "Book a call whenever suits you:\n"
            "\n"
            "{{ booking_url }}\n"
            "\n"
            "Warm regards,\n"
            "Ashley"
        ),
    },
    {
        "step_number": 3,
        "delay_days": 9,
        "template_name": "Franchise Brochure Follow-up 3 - Resilient Kid",
        "subject": "Let's talk about your Resilient Kid franchise",
        "body": (
            "Hi {{ recipient_name }},\n"
            "\n"
            "REPLACE ME - Ashley's own follow-up copy goes here.\n"
            "\n"
            "{{ booking_url }}\n"
            "\n"
            "Warm regards,\n"
            "Ashley"
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


def _ensure_email_template(meta, body_fieldname, template_name, subject, body):
    if frappe.db.exists("Email Template", template_name):
        doc = frappe.get_doc("Email Template", template_name)

        if not _is_blank(doc.get("subject")) or not _is_blank(doc.get(body_fieldname)):
            return

        if meta.has_field("subject"):
            doc.subject = subject

        doc.set(body_fieldname, body)
        doc.save(ignore_permissions=True)
    else:
        doc = frappe.new_doc("Email Template")
        doc.name = template_name

        if meta.has_field("subject"):
            doc.subject = subject

        doc.set(body_fieldname, body)
        doc.insert(ignore_permissions=True)


def execute():
    if not frappe.db.exists("DocType", "Email Template"):
        return
    if not frappe.db.exists("DocType", "Email Sequence"):
        return

    meta = frappe.get_meta("Email Template")
    body_fieldname = _body_fieldname(meta)

    if not body_fieldname:
        frappe.log_error(
            f"Email Template has none of the expected body fields {BODY_FIELD_CANDIDATES}.",
            "Create Franchise Brochure Nurture Sequence - No Body Field Found",
        )
        return

    try:
        for step in STEPS:
            _ensure_email_template(meta, body_fieldname, step["template_name"], step["subject"], step["body"])

        if frappe.db.exists("Email Sequence", SEQUENCE_NAME):
            frappe.db.commit()
            return

        sequence = frappe.get_doc({
            "doctype": "Email Sequence",
            "sequence_name": SEQUENCE_NAME,
            "description": (
                "Follow-up emails after someone requests the franchise brochure. "
                "Review/replace the placeholder copy in each step's Email Template, "
                "then switch Is Active on before this sends to anyone."
            ),
            "is_active": 0,
            "trigger_doctype": TRIGGER_DOCTYPE,
            "trigger_email_field": "email",
            "trigger_name_field": "full_name",
            "steps": [
                {
                    "step_number": step["step_number"],
                    "delay_days": step["delay_days"],
                    "email_template": step["template_name"],
                }
                for step in STEPS
            ],
        })
        sequence.insert(ignore_permissions=True)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Create Franchise Brochure Nurture Sequence Failed")

    frappe.db.commit()
