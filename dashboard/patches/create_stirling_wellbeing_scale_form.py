"""
Creates the Stirling Children's Wellbeing Scale as a real DocType + Web
Form, the same way every other Reports-section "form" on this site already
works (see form_reports.py's own module docstring) - a custom (Desk-style)
DocType discovered automatically once its Module is "Forms", with a public
Web Form on top. Built here instead of by hand in Desk so it ships with
the rest of this deploy, with no manual DocType-builder/Web-Form-builder
steps needed afterwards.

The scale itself: 15 published statements, each answered on a 1-5 "Never"
to "All of the time" scale. Scored into a 12-item wellbeing total and a
3-item Social Desirability validity check - see
wellbeing_forms.compute_stirling_wellbeing_score (hooked on this DocType's
validate event in hooks.py) for the actual scoring, which a custom=1
DocType can't hold as its own file-based controller.

Fully anonymous by design (no name/identifying field at all, per how this
was actually asked for) - the Web Form's own login_required=0 + anonymous=1
covers guest submission; Frappe's Web Form.accept() inserts with
ignore_permissions=True for exactly this case, so no Guest DocType
permission is needed (see web_form.py). Visible in the franchisor
dashboard's Reports section only for now (custom_show_in_franchisor_reports
on the Web Form; see form_reports.sync_web_form_report_visibility) - ticking
"Show In Coach Reports" on the Web Form later is all it'd take to extend
this to coaches too.

Runs automatically on the next `bench migrate` (part of a normal deploy) -
no manual step needed.
"""

import frappe

DOCTYPE_NAME = "Stirling Wellbeing Response"
WEB_FORM_ROUTE = "wellbeing-check-in"

SCALE_OPTIONS = "\n".join([
    "1 - Never",
    "2 - Not much of the time",
    "3 - Some of the time",
    "4 - Quite a lot of the time",
    "5 - All of the time",
])

# (item number, statement) - verbatim from the published scale.
STATEMENTS = [
    (1, "I think good things will happen in my life"),
    (2, "I have always told the truth"),
    (3, "I've been able to make choices easily"),
    (4, "I can find lots of fun things to do"),
    (5, "I feel that I am good at some things"),
    (6, "I think lots of people care about me"),
    (7, "I like everyone I have met"),
    (8, "I think there are many things I can be proud of"),
    (9, "I've been feeling calm"),
    (10, "I've been in a good mood"),
    (11, "I enjoy what each new day brings"),
    (12, "I've been getting on well with people"),
    (13, "I always share my sweets"),
    (14, "I've been cheerful about things"),
    (15, "I've been feeling relaxed"),
]


def execute():
    _create_doctype()
    _create_web_form()


def _create_doctype():
    if frappe.db.exists("DocType", DOCTYPE_NAME):
        return

    fields = []
    for number, statement in STATEMENTS:
        fields.append({
            "fieldname": f"q{number}",
            "fieldtype": "Select",
            "label": statement,
            "options": SCALE_OPTIONS,
            "reqd": 1,
        })

    fields.append({
        "fieldname": "results_section",
        "fieldtype": "Section Break",
        "label": "Results",
    })
    fields.append({
        "fieldname": "wellbeing_score",
        "fieldtype": "Int",
        "label": "Wellbeing Score (out of 60)",
        "read_only": 1,
    })
    fields.append({
        "fieldname": "social_desirability_score",
        "fieldtype": "Int",
        "label": "Social Desirability Score (out of 15)",
        "read_only": 1,
        "description": "A score of 3, or 14-15, means the wellbeing score above should be treated with caution.",
    })
    fields.append({
        "fieldname": "validity_caution",
        "fieldtype": "Check",
        "label": "Treat With Caution",
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
        {
            "fieldname": f"q{number}",
            "fieldtype": "Select",
            "label": statement,
            "options": SCALE_OPTIONS,
            "reqd": 1,
        }
        for number, statement in STATEMENTS
    ]

    doc = frappe.get_doc({
        "doctype": "Web Form",
        "title": "Children's Wellbeing Check-In",
        "route": WEB_FORM_ROUTE,
        "doc_type": DOCTYPE_NAME,
        "module": "Dashboard",
        "is_standard": 0,
        "published": 1,
        "login_required": 0,
        "anonymous": 1,
        "introduction_text": (
            "<p>Here are some statements about how you might have been feeling or "
            "thinking about things over the past couple of weeks. For each one, pick "
            "the answer that feels most true for you - there are no right or wrong "
            "answers!</p>"
        ),
        "button_label": "Submit",
        "success_title": "Thank you!",
        "success_message": "All done - thanks for sharing how you've been feeling.",
        "web_form_fields": web_form_fields,
        "custom_show_in_franchisor_reports": 1,
        "custom_show_in_coach_reports": 0,
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
