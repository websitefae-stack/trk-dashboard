"""
Ashley asked for two additions to the already-live Student Resilience
Survey (see create_student_resilience_survey_form.py's own docstring
for how it was built): a Year Group field, and an explicit privacy
statement telling students their personal info isn't collected by or
shared with their school.

Adds year_group to both the underlying DocType (Student Resilience
Survey Response) and the public Web Form, right after the name fields,
and appends the privacy statement to the Web Form's introduction text.
Safe to re-run - skips whatever's already in place.
"""

import frappe

DOCTYPE_NAME = "Student Resilience Survey Response"
WEB_FORM_ROUTE = "student-resilience-survey"

YEAR_GROUP_OPTIONS = (
    "Reception\nYear 1\nYear 2\nYear 3\nYear 4\nYear 5\nYear 6\n"
    "Year 7\nYear 8\nYear 9\nYear 10\nYear 11\nYear 12\nYear 13\nOther"
)

PRIVACY_STATEMENT = (
    "<p><strong>Your privacy:</strong> none of your personal information is collected by your "
    "school or shared with your school. Your name is only used to match up your Before and "
    "After surveys - your school never sees your individual answers.</p>"
)


def _year_group_field(kind):
    field = {
        "fieldname": "year_group",
        "fieldtype": "Select",
        "label": "Year Group",
        "options": YEAR_GROUP_OPTIONS,
        "reqd": 1,
    }
    if kind == "doctype":
        field["in_list_view"] = 1
        field["in_standard_filter"] = 1
    return field


def execute():
    _add_to_doctype()
    _add_to_web_form()


def _add_to_doctype():
    if not frappe.db.exists("DocType", DOCTYPE_NAME):
        return

    doc = frappe.get_doc("DocType", DOCTYPE_NAME)

    if any(f.fieldname == "year_group" for f in doc.fields):
        return

    insert_at = next(
        (i for i, f in enumerate(doc.fields) if f.fieldname == "survey_stage"),
        len(doc.fields),
    )
    doc.append("fields", _year_group_field("doctype"))
    doc.fields.insert(insert_at, doc.fields.pop())
    doc.save(ignore_permissions=True)
    frappe.db.commit()


def _add_to_web_form():
    if not frappe.db.exists("Web Form", {"route": WEB_FORM_ROUTE}):
        return
    if not frappe.db.exists("DocType", DOCTYPE_NAME):
        return

    web_form = frappe.get_doc("Web Form", {"route": WEB_FORM_ROUTE})

    if PRIVACY_STATEMENT not in (web_form.introduction_text or ""):
        web_form.introduction_text = (web_form.introduction_text or "") + PRIVACY_STATEMENT

    if not any(f.fieldname == "year_group" for f in web_form.web_form_fields):
        insert_at = next(
            (i for i, f in enumerate(web_form.web_form_fields) if f.fieldname == "survey_stage"),
            len(web_form.web_form_fields),
        )
        web_form.append("web_form_fields", _year_group_field("web_form"))
        web_form.web_form_fields.insert(insert_at, web_form.web_form_fields.pop())

    web_form.save(ignore_permissions=True)
    frappe.db.commit()
