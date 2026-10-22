"""
One-off, read-only diagnostic (same technique as diag_cara_coaching_
pack_visibility.py/diag_cara_coaching_pack_raw_sql.py earlier in this
app's history) - Ashley submitted a fresh Before and After Stirling
Wellbeing Check-In response using the now-fixed school picker, but the
"Children's Wellbeing (Before/After)" Reports tab still shows no
school to pick and no results, even though the same submissions show
up fine in the generic Form Results tab.

Rather than guess at another fix blind, this writes the raw school/
student_first_name/student_last_name/survey_stage/creation values of
the 10 most recent Stirling Wellbeing Response records to the Error
Log, so the actual saved data - not a guess about it - can drive the
next fix. Safe to delete once the cause is found.
"""

import frappe

from dashboard.patches.create_stirling_wellbeing_scale_form import DOCTYPE_NAME


def execute():
    if not frappe.db.exists("DocType", DOCTYPE_NAME):
        frappe.log_error(f"{DOCTYPE_NAME} doctype does not exist", "Diag: Stirling recent responses")
        return

    meta = frappe.get_meta(DOCTYPE_NAME)
    field_info = {
        f.fieldname: {"fieldtype": f.fieldtype, "options": f.options, "reqd": f.reqd}
        for f in meta.fields
        if f.fieldname in ("school", "student_first_name", "student_last_name", "survey_stage")
    }

    rows = frappe.get_all(
        DOCTYPE_NAME,
        fields=["name", "creation", "school", "student_first_name", "student_last_name", "survey_stage"],
        order_by="creation desc",
        limit_page_length=10,
        ignore_permissions=True,
    )

    message = (
        f"DocType field definitions (school/name/stage):\n{field_info}\n\n"
        f"10 most recent {DOCTYPE_NAME} rows:\n"
        + "\n".join(str(row) for row in rows)
    )

    frappe.log_error(message, "Diag: Stirling recent responses")
