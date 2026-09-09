"""
Creates the "Relationships with staff" questionnaire (Wellbeing
Measurement for Schools, Anna Freud / CORC) as a real DocType + Web Form -
see create_school_experience_form.py's own module docstring for why this
is built by patch, the same way every other Reports-section form on this
site already works.

4 statements ("At school, there is an adult who..."), each scored 1-5 -
see staff_relationships_form.py (hooked on this DocType's validate event
in hooks.py) for the scoring.

Captures Name and Year Group as plain free text, NOT linked to an
existing Client record - same as the care languages quiz. Franchisor-only
Reports visibility for now, same as the other forms.

Runs automatically on the next `bench migrate` (part of a normal deploy) -
no manual step needed.
"""

import frappe

DOCTYPE_NAME = "Relationships With Staff Response"
WEB_FORM_ROUTE = "relationships-with-staff"

YEAR_GROUP_OPTIONS = "\n".join([
    "Reception", "Year 1", "Year 2", "Year 3", "Year 4", "Year 5", "Year 6",
    "Year 7", "Year 8", "Year 9", "Year 10", "Year 11", "Year 12", "Year 13", "Other",
])

# Only the two endpoints are labelled on the published scale itself (1 =
# Never, 5 = Always) - the middle three are left as plain numbers on a
# single continuous scale, same as the source questionnaire shows them.
SCALE_OPTIONS = "\n".join(["1 - Never", "2", "3", "4", "5 - Always"])

STATEMENTS = [
    (1, "Really cares about me"),
    (2, "Tells me when I do a good job"),
    (3, "Believes that I will be a success"),
    (4, "I trust"),
]


def execute():
    _create_doctype()
    _create_web_form()


def _create_doctype():
    if frappe.db.exists("DocType", DOCTYPE_NAME):
        return

    fields = [
        {"fieldname": "pupil_name", "fieldtype": "Data", "label": "Name", "reqd": 1},
        {
            "fieldname": "year_group",
            "fieldtype": "Select",
            "label": "Year Group",
            "options": YEAR_GROUP_OPTIONS,
            "reqd": 1,
        },
    ]

    for number, statement in STATEMENTS:
        fields.append({
            "fieldname": f"q{number}",
            "fieldtype": "Select",
            "label": statement,
            "options": SCALE_OPTIONS,
            "reqd": 1,
        })

    fields.append({"fieldname": "results_section", "fieldtype": "Section Break", "label": "Results"})
    fields.append({
        "fieldname": "total_score",
        "fieldtype": "Int",
        "label": "Total Score (out of 20)",
        "read_only": 1,
    })

    doc = frappe.get_doc({
        "doctype": "DocType",
        "name": DOCTYPE_NAME,
        "module": "Dashboard",
        "custom": 1,
        "naming_rule": "Autoincrement",
        "autoname": "autoincrement",
        "fields": fields,
        "permissions": [
            {
                "role": "System Manager",
                "read": 1, "write": 1, "create": 1, "delete": 1,
                "report": 1, "export": 1, "print": 1, "email": 1, "share": 1,
            },
        ],
        "sort_field": "creation",
        "sort_order": "DESC",
        "track_changes": 1,
    })
    doc.insert(ignore_permissions=True)


def _create_web_form():
    if frappe.db.exists("Web Form", {"route": WEB_FORM_ROUTE}):
        return
    if not frappe.db.exists("DocType", DOCTYPE_NAME):
        return

    web_form_fields = [
        {"fieldname": "pupil_name", "fieldtype": "Data", "label": "Name", "reqd": 1},
        {
            "fieldname": "year_group",
            "fieldtype": "Select",
            "label": "Year Group",
            "options": YEAR_GROUP_OPTIONS,
            "reqd": 1,
        },
    ]
    for number, statement in STATEMENTS:
        web_form_fields.append({
            "fieldname": f"q{number}",
            "fieldtype": "Select",
            "label": statement,
            "options": SCALE_OPTIONS,
            "reqd": 1,
        })

    doc = frappe.get_doc({
        "doctype": "Web Form",
        "title": "Relationships With Staff",
        "route": WEB_FORM_ROUTE,
        "doc_type": DOCTYPE_NAME,
        "module": "Dashboard",
        "is_standard": 0,
        "published": 1,
        "login_required": 0,
        "anonymous": 1,
        "introduction_text": (
            "<p>Please read every statement carefully and pick the answer that fits you best.</p>"
            "<p><strong>At school, there is an adult who:</strong></p>"
        ),
        "button_label": "Submit",
        "success_title": "Thank you!",
        "success_message": "All done - thanks for sharing!",
        "web_form_fields": web_form_fields,
        "custom_show_in_franchisor_reports": 1,
        "custom_show_in_coach_reports": 0,
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
