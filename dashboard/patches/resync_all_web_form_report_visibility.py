"""
sync_web_form_report_visibility only ever ran as Web Form's own
on_update hook until this same deploy added after_insert too (see
hooks.py) - confirmed live that a form patch's own doc.insert() could
leave a brand new Web Form without the Form Visibility Rule its "Show
In Franchisor/Coach Reports" ticks actually depend on, invisible under
Links/Reports despite both being on (Teacher Session Feedback was the
one actually reported missing).

One-off reconciliation so this fixes itself on this deploy rather than
needing a manual repair call per form - re-runs the exact same sync
against every currently published Web Form. It's a plain upsert, so
running it against a form that was already fine is a no-op.
"""

import frappe

from dashboard.api.shared.form_reports import sync_web_form_report_visibility


def execute():
    web_form_names = frappe.get_all("Web Form", filters={"published": 1}, pluck="name")

    for web_form_name in web_form_names:
        try:
            doc = frappe.get_doc("Web Form", web_form_name)
            sync_web_form_report_visibility(doc)
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Web Form Visibility Resync Failed - {web_form_name}")

    frappe.db.commit()
