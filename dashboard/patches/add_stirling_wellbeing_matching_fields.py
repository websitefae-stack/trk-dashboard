"""
Adds the same Before/After matching capability the Student Resilience
Survey already has (see create_student_resilience_survey_form.py and
enable_student_resilience_survey_reports_visibility.py) to the Stirling
Children's Wellbeing Check-In - it's also completed twice per child and
previously had no way to pair the two up.

Originally built fully anonymous, with no identifying field at all (see
create_stirling_wellbeing_scale_form.py's own docstring) - adds Student
First/Last Name as the matching key, the same choice Ashley made for
the Resilience Survey over a self-generated anonymous code (a child
risks failing to reproduce an anonymous code identically the second
time, breaking the pairing), a Survey Stage (Before/After), and a
School link - Ashley confirmed this one should also record which
school, same as the Resilience Survey, so two different children
sharing a name at different schools are never mixed up.

Inserted at the START of the existing field list (ahead of the
existing q1-q15 statements) on both the DocType and the Web Form, using
doc.append() + a reorder rather than reassigning the whole list, since
append() is the only way Frappe reliably turns a plain dict into a real
child-table row - see add_school_sequence_enrollment_previous_stage.py
for the same pattern on a plain append (no reordering needed there).
Existing historical responses, saved before these fields existed,
simply have them blank; they're correctly treated by the comparison
report as "no matching pair" rather than retroactively guessed at.

This form is no longer fully anonymous data (names are collected), the
same tradeoff the Resilience Survey already made - but, also like that
one, a coach or the franchisor is never actually shown a name: see
form_reports.py's FORM_HIDDEN_FIELDNAMES (extended here to cover this
DocType's two name fields too) and wellbeing_forms.py's own dedicated,
anonymised Before/After comparison report.
"""

import frappe

STIRLING_DOCTYPE = "Stirling Wellbeing Response"
WEB_FORM_ROUTE = "wellbeing-check-in"
SCHOOL_DOCTYPE = "School"


def execute():
    _update_doctype()
    _update_web_form()


def _doctype_new_fields():
    fields = [
        {
            "fieldname": "student_first_name",
            "fieldtype": "Data",
            "label": "Student First Name",
            "reqd": 1,
            "in_list_view": 1,
        },
        {
            "fieldname": "student_last_name",
            "fieldtype": "Data",
            "label": "Student Last Name",
            "reqd": 1,
            "in_list_view": 1,
        },
        {
            "fieldname": "survey_stage",
            "fieldtype": "Select",
            "label": "Survey Stage",
            "options": "Before\nAfter",
            "reqd": 1,
            "in_list_view": 1,
            "in_standard_filter": 1,
            "description": "Lets a Before and After response from the same student be told apart.",
        },
    ]

    if frappe.db.exists("DocType", SCHOOL_DOCTYPE):
        fields.append({
            "fieldname": "school",
            "fieldtype": "Link",
            "label": "School",
            "options": SCHOOL_DOCTYPE,
            "reqd": 1,
            "in_list_view": 1,
            "in_standard_filter": 1,
        })

    fields.append({
        "fieldname": "responses_section",
        "fieldtype": "Section Break",
        "label": "Responses",
    })

    return fields


def _web_form_new_fields():
    fields = [
        {
            "fieldname": "student_first_name",
            "fieldtype": "Data",
            "label": "First Name",
            "reqd": 1,
        },
        {
            "fieldname": "student_last_name",
            "fieldtype": "Data",
            "label": "Last Name",
            "reqd": 1,
            "description": "Use the same spelling both times you complete this, so your two check-ins can be matched up.",
        },
        {
            "fieldname": "survey_stage",
            "fieldtype": "Select",
            "label": "Is this your Before or After check-in?",
            "options": "Before\nAfter",
            "reqd": 1,
        },
    ]

    if frappe.db.exists("DocType", SCHOOL_DOCTYPE):
        fields.append({
            "fieldname": "school",
            "fieldtype": "Link",
            "label": "School",
            "options": SCHOOL_DOCTYPE,
            "reqd": 1,
        })

    fields.append({
        "fieldname": "responses_section",
        "fieldtype": "Section Break",
        "label": "Responses",
    })

    return fields


def _update_doctype():
    if not frappe.db.exists("DocType", STIRLING_DOCTYPE):
        return

    doc = frappe.get_doc("DocType", STIRLING_DOCTYPE)
    existing_fieldnames = {f.fieldname for f in doc.fields}

    if "student_first_name" in existing_fieldnames:
        return

    new_fields = _doctype_new_fields()
    for field_dict in new_fields:
        doc.append("fields", field_dict)

    doc.fields = doc.fields[-len(new_fields):] + doc.fields[:-len(new_fields)]
    doc.save(ignore_permissions=True)
    frappe.clear_cache(doctype=STIRLING_DOCTYPE)


def _update_web_form():
    name = frappe.db.exists("Web Form", {"route": WEB_FORM_ROUTE})
    if not name:
        return

    doc = frappe.get_doc("Web Form", name)
    existing_fieldnames = {f.fieldname for f in doc.web_form_fields}

    if "student_first_name" in existing_fieldnames:
        return

    new_fields = _web_form_new_fields()
    for field_dict in new_fields:
        doc.append("web_form_fields", field_dict)

    doc.web_form_fields = doc.web_form_fields[-len(new_fields):] + doc.web_form_fields[:-len(new_fields)]
    doc.anonymous = 0

    # Was franchisor-only (see create_stirling_wellbeing_scale_form.py) -
    # the Before/After comparison this patch enables is, like the
    # Resilience Survey's, meant for coaches too, not just the franchisor.
    doc.custom_show_in_coach_reports = 1

    doc.save(ignore_permissions=True)
    frappe.db.commit()

    from dashboard.api.shared.form_reports import sync_web_form_report_visibility
    sync_web_form_report_visibility(doc)
