"""
Removes the custom_email_account Custom Field from Coach, added by
add_coach_email_account_link_field.py in error - Coach already carries
"user" (the coach's Frappe login) and "coach_email" (their Workspace
address), which is exactly what google_mail_connect.py's
_get_email_account_row() matches an Email Account against. A third field
duplicating that link was unnecessary; this undoes it on any site that
already ran the earlier patch.
"""

import frappe


def execute():
    field_name = "Coach-custom_email_account"

    if frappe.db.exists("Custom Field", field_name):
        frappe.delete_doc("Custom Field", field_name, ignore_permissions=True, force=True)
        frappe.clear_cache(doctype="Coach")
        frappe.db.commit()
