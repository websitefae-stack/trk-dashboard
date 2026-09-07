"""
Re-runs add_lms_course_show_on_website_field.py's own backfill (setting
custom_show_on_website = 1 for every course that's Published and not
Restricted, so today's real catalogue doesn't disappear) - in case that
first run didn't actually reach production (a migrate that didn't run
yet, or ran before the field itself existed on that request). Safe to
run again regardless - it only ever sets the same value the same way.
"""

import frappe


def execute():
    if not frappe.db.exists("DocType", "LMS Course"):
        return

    if not frappe.db.has_column("LMS Course", "custom_show_on_website"):
        return

    frappe.db.sql(
        """
        update `tabLMS Course`
        set custom_show_on_website = 1
        where published = 1
          and ifnull(custom_hq_restricted, 0) = 0
        """
    )
    frappe.db.commit()
