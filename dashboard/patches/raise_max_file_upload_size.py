"""
Coaches attaching a downloadable zip (e.g. an audio track pack) to a
Course Lesson were hitting a 25 MB upload cap - this may be a Frappe
Cloud hosting limit rather than a site setting (unverified from here),
but raising the site's own System Settings > Max File Size can only
help, never hurt, so it's done regardless.

Runs automatically on the next `bench migrate`. Safe to run more than
once - only raises the value, never lowers a deliberately-set one.
"""

import frappe

RAISED_MAX_FILE_SIZE_MB = 100


def execute():
    meta = frappe.get_meta("System Settings")

    if not meta.has_field("max_file_size"):
        return

    current = frappe.db.get_single_value("System Settings", "max_file_size")

    if current and current >= RAISED_MAX_FILE_SIZE_MB:
        return

    frappe.db.set_single_value("System Settings", "max_file_size", RAISED_MAX_FILE_SIZE_MB)
    frappe.db.commit()
