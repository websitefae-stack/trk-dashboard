"""
Creates the School Pipeline: five custom DocTypes for running the school
outreach campaign end to end from the franchisor dashboard -

- School: one prospective school (~600 of them). Deliberately NOT a
  Client - a school only gets linked to (or turned into) a real Client
  the moment it actually buys something, via linked_client. Until then
  it's a lightweight record living entirely in this pipeline, so the
  Client list isn't cluttered with hundreds of schools that may never
  convert (same reasoning as the existing Online Client doctype).
- School Contact (child table of School): a named person at the school
  (SENCO/Head/Reception/Other) - sequence emails go out to the whole
  group at once (see school_pipeline.py), but response_note/responded
  are tracked per contact, since it might be the SENCO who replies and
  not the Head.
- School Sequence: a reusable named template (e.g. "Autumn Outreach"),
  built and edited entirely from the franchisor dashboard - an ordered
  list of steps, each pointing at an Email Template (reusing Frappe's
  own Email Template doctype, same as every other outgoing email in
  this app) and how many days after the previous step to send it.
- School Sequence Step (child table of School Sequence): one email in
  the sequence.
- School Sequence Enrollment: one run of one Sequence against one
  School - deliberately its own record rather than a single "current
  sequence" field on School, so a school can go through several
  sequences over months/years without the history being overwritten,
  and a new sequence can always be started regardless of what happened
  with a previous one (see school_pipeline.py's module docstring for
  the full reasoning).

Runs automatically on the next `bench migrate` - no manual step needed.
"""

import frappe

SCHOOL_CONTACT_DOCTYPE = "School Contact"
SCHOOL_DOCTYPE = "School"
SEQUENCE_STEP_DOCTYPE = "School Sequence Step"
SEQUENCE_DOCTYPE = "School Sequence"
ENROLLMENT_DOCTYPE = "School Sequence Enrollment"


def execute():
    _create_school_contact_doctype()
    _create_school_doctype()
    _create_sequence_step_doctype()
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


def _create_school_contact_doctype():
    if frappe.db.exists("DocType", SCHOOL_CONTACT_DOCTYPE):
        return

    doc = frappe.get_doc({
        "doctype": "DocType",
        "name": SCHOOL_CONTACT_DOCTYPE,
        "module": "Dashboard",
        "custom": 1,
        "istable": 1,
        "editable_grid": 1,
        "fields": [
            {"fieldname": "contact_name", "fieldtype": "Data", "label": "Name", "reqd": 1, "in_list_view": 1},
            {
                "fieldname": "role",
                "fieldtype": "Select",
                "label": "Role",
                "options": "\nSENCO\nHead\nDeputy Head\nReception\nOther",
                "in_list_view": 1,
            },
            {"fieldname": "email", "fieldtype": "Data", "options": "Email", "label": "Email", "reqd": 1, "in_list_view": 1},
            {"fieldname": "responded", "fieldtype": "Check", "label": "Responded", "in_list_view": 1},
            {
                "fieldname": "response_note",
                "fieldtype": "Small Text",
                "label": "Response Note",
                "description": "What they said, and any follow-up needed - shown against this contact specifically.",
            },
        ],
        "permissions": _managed_permissions(),
    })
    doc.insert(ignore_permissions=True)


def _create_school_doctype():
    if frappe.db.exists("DocType", SCHOOL_DOCTYPE):
        return

    doc = frappe.get_doc({
        "doctype": "DocType",
        "name": SCHOOL_DOCTYPE,
        "module": "Dashboard",
        "custom": 1,
        "naming_rule": "Autoincrement",
        "autoname": "autoincrement",
        "fields": [
            {"fieldname": "school_name", "fieldtype": "Data", "label": "School Name", "reqd": 1, "in_list_view": 1},
            {"fieldname": "website", "fieldtype": "Data", "label": "Website"},
            {"fieldname": "address", "fieldtype": "Small Text", "label": "Address"},
            {"fieldname": "telephone", "fieldtype": "Data", "label": "Telephone"},
            {"fieldname": "area", "fieldtype": "Data", "label": "Area", "in_list_view": 1, "in_standard_filter": 1},
            {
                "fieldname": "stage",
                "fieldtype": "Select",
                "label": "Stage",
                "options": "New\nIn Sequence\nIdle\nResponded\nCall Booked\nCustomer\nDeclined",
                "default": "New",
                "in_list_view": 1,
                "in_standard_filter": 1,
                "description": "Kept in sync automatically as sequences run and contacts respond - can also be moved by hand from the pipeline board.",
            },
            {
                "fieldname": "linked_client",
                "fieldtype": "Link",
                "options": "Client",
                "label": "Linked Client",
                "description": "Stays empty until this school actually buys something (or is manually linked, for a school that's already a customer) - see school_pipeline.py's convert_school_to_client.",
            },
            {
                "fieldname": "notes",
                "fieldtype": "Small Text",
                "label": "General Notes",
                "description": "Notes about the school itself, not tied to a specific contact's reply - see School Contact.response_note for that.",
            },
            {"fieldname": "contacts_section", "fieldtype": "Section Break", "label": "Contacts"},
            {
                "fieldname": "contacts",
                "fieldtype": "Table",
                "options": SCHOOL_CONTACT_DOCTYPE,
                "label": "Contacts",
            },
        ],
        "permissions": _managed_permissions(),
        "sort_field": "modified",
        "sort_order": "DESC",
        "track_changes": 1,
    })
    doc.insert(ignore_permissions=True)


def _create_sequence_step_doctype():
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
                "description": "For step 1, days after enrollment. 0 sends right away.",
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
                "fieldname": "school",
                "fieldtype": "Link",
                "options": SCHOOL_DOCTYPE,
                "label": "School",
                "reqd": 1,
                "in_list_view": 1,
            },
            {
                "fieldname": "sequence",
                "fieldtype": "Link",
                "options": SEQUENCE_DOCTYPE,
                "label": "Sequence",
                "reqd": 1,
                "in_list_view": 1,
            },
            {
                "fieldname": "status",
                "fieldtype": "Select",
                "options": "Active\nCompleted\nCancelled",
                "label": "Status",
                "default": "Active",
                "in_list_view": 1,
            },
            {"fieldname": "current_step", "fieldtype": "Int", "label": "Steps Sent So Far", "default": "0"},
            {"fieldname": "start_date", "fieldtype": "Date", "label": "Start Date", "reqd": 1, "in_list_view": 1},
            {"fieldname": "next_send_date", "fieldtype": "Date", "label": "Next Send Date", "in_list_view": 1},
            {"fieldname": "last_sent_on", "fieldtype": "Datetime", "label": "Last Sent On", "read_only": 1},
        ],
        "permissions": _managed_permissions(),
        "sort_field": "creation",
        "sort_order": "DESC",
        "track_changes": 1,
    })
    doc.insert(ignore_permissions=True)
