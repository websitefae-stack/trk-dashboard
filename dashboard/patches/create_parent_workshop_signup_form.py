"""
Creates a generic Parent Workshop Sign-Up as a real DocType + Web Form,
the same pattern every other public form on this site already follows
(see create_student_resilience_survey_form.py's own module docstring).

Ashley's own spec: one generic sign-up sheet shared by every parent
workshop (not tied to a specific workshop or date) - name, surname,
email, and the child's year group. Nothing else was asked for, so
nothing else is collected here.

Runs automatically on the next `bench migrate` - no manual step needed.
"""

import frappe

DOCTYPE_NAME = "Parent Workshop Signup"
WEB_FORM_ROUTE = "parent-workshop-signup"

# Same list already used for the Student Resilience Survey's own Year
# Group field (add_year_group_and_privacy_notice_to_resilience_survey.py)
# - kept identical so the two forms don't disagree on what a year group
# actually is.
YEAR_GROUP_OPTIONS = (
    "Reception\nYear 1\nYear 2\nYear 3\nYear 4\nYear 5\nYear 6\n"
    "Year 7\nYear 8\nYear 9\nYear 10\nYear 11\nYear 12\nYear 13\nOther"
)


def execute():
    _create_doctype()
    _create_web_form()


def _signup_fields():
    return [
        {
            "fieldname": "first_name",
            "fieldtype": "Data",
            "label": "First Name",
            "reqd": 1,
            "in_list_view": 1,
        },
        {
            "fieldname": "last_name",
            "fieldtype": "Data",
            "label": "Surname",
            "reqd": 1,
            "in_list_view": 1,
        },
        {
            "fieldname": "email",
            "fieldtype": "Data",
            "options": "Email",
            "label": "Email",
            "reqd": 1,
            "in_list_view": 1,
        },
        {
            "fieldname": "child_year_group",
            "fieldtype": "Select",
            "label": "Child's Year Group",
            "options": YEAR_GROUP_OPTIONS,
            "reqd": 1,
            "in_list_view": 1,
        },
    ]


def _create_doctype():
    if frappe.db.exists("DocType", DOCTYPE_NAME):
        return

    doc = frappe.get_doc({
        "doctype": "DocType",
        "name": DOCTYPE_NAME,
        "module": "Dashboard",
        "custom": 1,
        "naming_rule": "Autoincrement",
        "autoname": "autoincrement",
        "fields": _signup_fields(),
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

    doc = frappe.get_doc({
        "doctype": "Web Form",
        "title": "Parent Workshop Sign-Up",
        "route": WEB_FORM_ROUTE,
        "doc_type": DOCTYPE_NAME,
        "module": "Dashboard",
        "is_standard": 0,
        "published": 1,
        "login_required": 0,
        "anonymous": 0,
        "introduction_text": "<p>Sign up here if you'd like to attend one of our parent workshops.</p>",
        "button_label": "Sign Up",
        "success_title": "Thank you!",
        "success_message": "You're signed up - we'll be in touch with the details.",
        "web_form_fields": _signup_fields(),
        "custom_show_in_franchisor_reports": 1,
        "custom_show_in_coach_reports": 1,
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
