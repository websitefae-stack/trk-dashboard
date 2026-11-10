"""
Repairs the "School" DocType after an accidental regression.

School Pipeline's create_school_pipeline_doctypes.py created "School" as
a database-only custom DocType (custom=1, naming_rule=Autoincrement) -
there was never a dashboard/dashboard/doctype/school/school.json file
for it, same as every other School field addition since
(add_school_address_and_telephone.py, add_school_area_and_deputy_head_role.py).

Building School Safeguarding Assurance Letters added exactly such a
json folder, meaning to extend School with four convenience fields
(postcode, default_contact_name, default_contact_role,
default_contact_email). Because School already existed, the next
`bench migrate` treated that json as School's authoritative schema and
resynced the live DocType down to just the fields it listed - wiping
website, telephone, area, stage, linked_client, notes and the contacts
child table field, and flipping naming from Autoincrement to
field:school_name. That's what produced:
    AttributeError: 'School' object has no attribute 'contacts'
on franchisor_db/client_details and the School Pipeline board.

The json folder has been deleted in the same change. This patch
restores every original field (same definitions as
create_school_pipeline_doctypes.py) if missing, re-adds the four
Safeguarding Letters fields if missing, puts naming back to
Autoincrement, and drops the "unique" constraint accidentally added to
school_name (never part of the original design - with ~600 schools,
duplicate names are expected, e.g. two different towns' "St Mary's").

Any data actually held in the now-missing columns (stage/area/telephone/
notes/linked_client/website for schools already in the pipeline) cannot
be recovered by this patch - it only restores the schema. If the
regression's migrate already ran against production, check the host's
database backup from just before that deploy for those values if School
Pipeline data looks reset.
"""

import frappe

SCHOOL_DOCTYPE = "School"
SCHOOL_CONTACT_DOCTYPE = "School Contact"

ORIGINAL_FIELDS = [
    {"fieldname": "website", "fieldtype": "Data", "label": "Website"},
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
]

NEW_SAFEGUARDING_LETTER_FIELDS = [
    {"fieldname": "postcode", "fieldtype": "Data", "label": "Postcode", "in_list_view": 1},
    {"fieldname": "sgl_column_break_1", "fieldtype": "Column Break"},
    {
        "fieldname": "default_contact_name",
        "fieldtype": "Data",
        "label": "Usual Safeguarding Contact Name",
        "description": "Pre-fills a new assurance letter request for this school - a coach can still type a different name/role/email for a specific request.",
    },
    {"fieldname": "default_contact_role", "fieldtype": "Data", "label": "Usual Contact Job Title"},
    {"fieldname": "default_contact_email", "fieldtype": "Data", "label": "Usual Contact Email", "options": "Email"},
]


def execute():
    if not frappe.db.exists("DocType", SCHOOL_DOCTYPE):
        return

    # Put naming back to Autoincrement straight in the DB first, bypassing
    # DocType.validate()'s own guard (which refuses to change to/from
    # Autoincrement through doc.save() once the doctype has data). Safe
    # here because this doesn't rename any existing school - every school
    # already has its original autoincrement docname regardless of what
    # the naming_rule setting says; this only corrects what *new* schools
    # get named with going forward. Doing it as a separate raw update
    # (rather than bundling it into the save() below) means the doc
    # loaded after this already reflects "Autoincrement" on both sides of
    # that validate() check, so the field-restore save() doesn't trip it.
    current_naming_rule = frappe.db.get_value("DocType", SCHOOL_DOCTYPE, "naming_rule")
    if current_naming_rule != "Autoincrement":
        frappe.db.set_value(
            "DocType",
            SCHOOL_DOCTYPE,
            {"naming_rule": "Autoincrement", "autoname": "autoincrement"},
            update_modified=False,
        )
        frappe.db.commit()
        frappe.clear_cache(doctype=SCHOOL_DOCTYPE)

    doc = frappe.get_doc("DocType", SCHOOL_DOCTYPE)
    existing_fieldnames = {field.fieldname for field in doc.fields}

    changed = False

    for field in ORIGINAL_FIELDS + NEW_SAFEGUARDING_LETTER_FIELDS:
        if field["fieldname"] not in existing_fieldnames:
            doc.append("fields", field)
            changed = True

    for field in doc.fields:
        if field.fieldname == "school_name" and field.unique:
            field.unique = 0
            changed = True

    if not doc.custom:
        doc.custom = 1
        changed = True

    if changed:
        doc.save(ignore_permissions=True)
        frappe.db.commit()
