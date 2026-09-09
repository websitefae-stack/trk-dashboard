"""
Creates the "How I feel cared for at school" care languages quiz as a real
DocType + Web Form, the same way every other Reports-section form on this
site already works (see form_reports.py's own module docstring) - a
custom (Desk-style) DocType discovered automatically once its Module is
"Forms", with a public Web Form on top.

16 questions, each a forced choice between two statements tied to one of
five "care languages" (Kind Words / Time Together / Helping Hands /
Little Surprises / High Fives) - see care_language_form.py (hooked on
this DocType's validate event in hooks.py, since a custom=1 DocType has
no file-based controller of its own) for the actual scoring.

Captures Name and Year Group as plain free text - explicitly NOT linked
to an existing Client record, per how this was actually asked for.
Visible in the franchisor dashboard's Reports section only for now
(custom_show_in_franchisor_reports on the Web Form; see
form_reports.sync_web_form_report_visibility) - ticking "Show In Coach
Reports" on the Web Form later is all it'd take to extend this to
coaches too.

Runs automatically on the next `bench migrate` (part of a normal deploy) -
no manual step needed.
"""

import frappe

from dashboard.api.shared.care_language_form import QUESTIONS, LANGUAGE_LABELS

DOCTYPE_NAME = "Care Language Response"
WEB_FORM_ROUTE = "care-languages-quiz"

YEAR_GROUP_OPTIONS = "\n".join([
    "Reception", "Year 1", "Year 2", "Year 3", "Year 4", "Year 5", "Year 6",
    "Year 7", "Year 8", "Year 9", "Year 10", "Year 11", "Year 12", "Year 13", "Other",
])

TOP_LANGUAGE_OPTIONS = "\n".join(LANGUAGE_LABELS.values())

_SCORE_FIELDS = [
    ("kind_words_score", "Kind Words"),
    ("time_together_score", "Time Together"),
    ("helping_hands_score", "Helping Hands"),
    ("little_surprises_score", "Little Surprises"),
    ("high_fives_score", "High Fives"),
]


def _question_options(options):
    return "\n".join(text for text, _letter in options)


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

    for number, options in QUESTIONS:
        fields.append({
            "fieldname": f"q{number}",
            "fieldtype": "Select",
            "label": f"Question {number}",
            "options": _question_options(options),
            "reqd": 1,
        })

    fields.append({"fieldname": "results_section", "fieldtype": "Section Break", "label": "Results"})
    for fieldname, label in _SCORE_FIELDS:
        fields.append({"fieldname": fieldname, "fieldtype": "Int", "label": label, "read_only": 1})
    fields.append({
        "fieldname": "top_care_language",
        "fieldtype": "Select",
        "label": "Top Care Language",
        "options": TOP_LANGUAGE_OPTIONS,
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
    for number, options in QUESTIONS:
        web_form_fields.append({
            "fieldname": f"q{number}",
            "fieldtype": "Select",
            "label": f"Question {number}",
            "options": _question_options(options),
            "reqd": 1,
        })

    doc = frappe.get_doc({
        "doctype": "Web Form",
        "title": "How I Feel Cared For At School",
        "route": WEB_FORM_ROUTE,
        "doc_type": DOCTYPE_NAME,
        "module": "Dashboard",
        "is_standard": 0,
        "published": 1,
        "login_required": 0,
        "anonymous": 1,
        "introduction_text": (
            "<p>Circle the ONE that feels MORE true for you. There's no wrong answer!</p>"
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
