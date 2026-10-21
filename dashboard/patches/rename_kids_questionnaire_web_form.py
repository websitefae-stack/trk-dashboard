"""
Renames the "Kids Questionnaire" Web Form's title to "Year 6
Questionnaire" (Ashley's own wording) - this is the field the Links
page reads for its display name (see form_reports.get_form_links,
which reads straight off the Web Form's own title) and it's also the
heading shown on the public form itself. The public URL
(/kids-questionnaire) is left exactly as it is, so any link already
shared, printed, or put on a QR code keeps working - only the label
people see changes.

This Web Form has no create_* patch anywhere in this repo (it was
built directly in Desk, not shipped as code), so there's no DocType-
level file to update - this patch is the only place this rename lives,
and it targets the one live record by its route, falling back to its
current title in case the route was ever changed by hand.
"""

import frappe

WEB_FORM_ROUTE = "kids-questionnaire"
OLD_TITLE = "Kids Questionnaire"
NEW_TITLE = "Year 6 Questionnaire"


def execute():
    web_form_name = frappe.db.get_value("Web Form", {"route": WEB_FORM_ROUTE}, "name")
    if not web_form_name:
        web_form_name = frappe.db.get_value("Web Form", {"title": OLD_TITLE}, "name")
    if not web_form_name:
        return

    frappe.db.set_value("Web Form", web_form_name, "title", NEW_TITLE)
    frappe.db.commit()
