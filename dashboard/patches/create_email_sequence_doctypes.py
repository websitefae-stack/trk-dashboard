"""
Creates the Email Sequence engine: three custom DocTypes managed
entirely from Frappe Desk, no code change needed to set up a new
sequence -

- Email Sequence: one automation (e.g. "Franchise Brochure Follow-Up"),
  with a trigger (trigger_doctype + trigger_email_field/
  trigger_name_field) and an ordered list of steps.
- Email Sequence Step (child table of Email Sequence): one email in
  the sequence - which Email Template to send (reusing Frappe's own
  Email Template doctype, same as every other outgoing email in this
  app - see email_templates.py) and how many days after the previous
  step (or enrollment, for step 1) to send it.
- Email Sequence Enrollment: one subscriber's progress through one
  sequence - created automatically by
  email_sequences.check_sequence_triggers (a wildcard after_insert
  hook - see hooks.py) whenever a new document of a sequence's
  trigger_doctype is created, and advanced by
  email_sequences.process_due_sequence_steps (a daily scheduled job).

Ashley creates/edits sequences and their steps as ordinary Desk
records - picking a Doctype to trigger off (e.g. "Franchise Brochure
Request", or eventually a Sales Invoice for a specific product), the
fieldname on that doctype holding the recipient's email, and as many
steps as she likes, each pointing at an Email Template she writes and
edits the same way she already edits any other email template on this
site.

Runs automatically on the next `bench migrate` - no manual step needed.
"""

import frappe

SEQUENCE_STEP_DOCTYPE = "Email Sequence Step"
SEQUENCE_DOCTYPE = "Email Sequence"
ENROLLMENT_DOCTYPE = "Email Sequence Enrollment"


def execute():
    _create_step_doctype()
    _create_sequence_doctype()
    _create_enrollment_doctype()


def _managed_permissions():
    return [
        {
            "role": "System Manager",
            "read": 1, "write": 1, "create": 1, "delete": 1,
            "report": 1, "export": 1, "print": 1, "email": 1, "share": 1,
        },
    ]


def _create_step_doctype():
    if frappe.db.exists("DocType", SEQUENCE_STEP_DOCTYPE):
        return

    doc = frappe.get_doc({
        "doctype": "DocType",
        "name": SEQUENCE_STEP_DOCTYPE,
        "module": "Dashboard",
        "custom": 1,
        "istable": 1,
        "editable_grid": 1,
        "fields": [
            {"fieldname": "step_number", "fieldtype": "Int", "label": "Step Number", "reqd": 1, "in_list_view": 1},
            {
                "fieldname": "delay_days",
                "fieldtype": "Int",
                "label": "Days After Previous Step",
                "description": "For step 1, days after enrollment (e.g. the brochure request). 0 sends right away.",
                "in_list_view": 1,
            },
            {
                "fieldname": "email_template",
                "fieldtype": "Link",
                "options": "Email Template",
                "label": "Email Template",
                "reqd": 1,
                "in_list_view": 1,
            },
        ],
        "permissions": _managed_permissions(),
    })
    doc.insert(ignore_permissions=True)


def _create_sequence_doctype():
    if frappe.db.exists("DocType", SEQUENCE_DOCTYPE):
        return

    doc = frappe.get_doc({
        "doctype": "DocType",
        "name": SEQUENCE_DOCTYPE,
        "module": "Dashboard",
        "custom": 1,
        "naming_rule": "By fieldname",
        "autoname": "field:sequence_name",
        "fields": [
            {"fieldname": "sequence_name", "fieldtype": "Data", "label": "Sequence Name", "reqd": 1, "unique": 1},
            {"fieldname": "description", "fieldtype": "Small Text", "label": "Description"},
            {"fieldname": "is_active", "fieldtype": "Check", "label": "Active", "default": "1"},
            {"fieldname": "trigger_section", "fieldtype": "Section Break", "label": "Trigger"},
            {
                "fieldname": "trigger_doctype",
                "fieldtype": "Link",
                "options": "DocType",
                "label": "Enrol Whenever a New Record of This Doctype Is Created",
                "reqd": 1,
                "description": (
                    "e.g. \"Franchise Brochure Request\" - any new document of this "
                    "doctype automatically enrols its recipient in this sequence."
                ),
            },
            {
                "fieldname": "trigger_email_field",
                "fieldtype": "Data",
                "label": "Fieldname Holding the Recipient's Email",
                "reqd": 1,
                "description": "e.g. \"email\" - the exact fieldname on the trigger doctype above.",
            },
            {
                "fieldname": "trigger_name_field",
                "fieldtype": "Data",
                "label": "Fieldname Holding the Recipient's Name (optional)",
                "description": "Used to personalise the emails - leave blank if there isn't one.",
            },
            {"fieldname": "steps_section", "fieldtype": "Section Break", "label": "Steps"},
            {
                "fieldname": "steps",
                "fieldtype": "Table",
                "options": SEQUENCE_STEP_DOCTYPE,
                "label": "Steps",
            },
        ],
        "permissions": _managed_permissions(),
        "sort_field": "modified",
        "sort_order": "DESC",
        "track_changes": 1,
    })
    doc.insert(ignore_permissions=True)


def _create_enrollment_doctype():
    if frappe.db.exists("DocType", ENROLLMENT_DOCTYPE):
        return

    doc = frappe.get_doc({
        "doctype": "DocType",
        "name": ENROLLMENT_DOCTYPE,
        "module": "Dashboard",
        "custom": 1,
        "naming_rule": "Autoincrement",
        "autoname": "autoincrement",
        "fields": [
            {
                "fieldname": "sequence",
                "fieldtype": "Link",
                "options": SEQUENCE_DOCTYPE,
                "label": "Sequence",
                "reqd": 1,
                "in_list_view": 1,
            },
            {"fieldname": "recipient_email", "fieldtype": "Data", "options": "Email", "label": "Recipient Email", "reqd": 1, "in_list_view": 1},
            {"fieldname": "recipient_name", "fieldtype": "Data", "label": "Recipient Name"},
            {"fieldname": "reference_doctype", "fieldtype": "Data", "label": "Reference Doctype", "read_only": 1},
            {"fieldname": "reference_name", "fieldtype": "Data", "label": "Reference Name", "read_only": 1},
            {
                "fieldname": "status",
                "fieldtype": "Select",
                "options": "Active\nCompleted\nCancelled",
                "label": "Status",
                "default": "Active",
                "in_list_view": 1,
            },
            {"fieldname": "current_step", "fieldtype": "Int", "label": "Steps Sent So Far", "default": "0"},
            {"fieldname": "next_send_date", "fieldtype": "Date", "label": "Next Send Date", "in_list_view": 1},
            {"fieldname": "last_sent_on", "fieldtype": "Datetime", "label": "Last Sent On", "read_only": 1},
        ],
        "permissions": _managed_permissions(),
        "sort_field": "creation",
        "sort_order": "DESC",
        "track_changes": 1,
    })
    doc.insert(ignore_permissions=True)
