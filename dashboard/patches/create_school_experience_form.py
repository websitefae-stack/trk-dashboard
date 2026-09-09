"""
Creates the "School experience" questionnaire (Wellbeing Measurement for
Schools, Anna Freud / CORC) as a real DocType + Web Form, the same way
every other Reports-section form on this site already works (see
form_reports.py's own module docstring) - a custom (Desk-style) DocType
discovered automatically once its Module is "Forms", with a public Web
Form on top.

4 statements, each scored 0-3 - see school_experience_form.py (hooked on
this DocType's validate event in hooks.py, since a custom=1 DocType has
no file-based controller of its own) for the scoring.

Captures Name and Year Group as plain free text, NOT linked to an
existing Client record - same as the care languages quiz. Visible in the
franchisor dashboard's Reports section only for now
(custom_show_in_franchisor_reports on the Web Form; see
form_reports.sync_web_form_report_visibility).

Runs automatically on the next `bench migrate` (part of a normal deploy) -
no manual step needed.
"""

import frappe

DOCTYPE_NAME = "School Experience Response"
WEB_FORM_ROUTE = "school-experience"

YEAR_GROUP_OPTIONS = "\n".join([
    "Reception", "Year 1", "Year 2", "Year 3", "Year 4", "Year 5", "Year 6",
    "Year 7", "Year 8", "Year 9", "Year 10", "Year 11", "Year 12", "Year 13", "Other",
])

SCALE_OPTIONS = "\n".join(["0 - Never", "1 - A little bit", "2 - A lot", "3 - Always"])

STATEMENTS = [
    (1, "I like going to school"),
    (2, "I get on well with my teachers"),
    (3, "I feel safe at school"),
    (4, "I feel like I belong at school"),
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
        "label": "Total Score (out of 12)",
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
        "title": "School Experience",
        "route": WEB_FORM_ROUTE,
        "doc_type": DOCTYPE_NAME,
        "module": "Dashboard",
        "is_standard": 0,
        "published": 1,
        "login_required": 0,
        "anonymous": 1,
        "introduction_text": (
            "<p>Below is a questionnaire about your life in school over the last few weeks. "
            "Please read every question. It is important you answer carefully about how you "
            "really feel. This is not a test, and there are no right or wrong answers. Your "
            "answers on this questionnaire are private.</p>"
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
