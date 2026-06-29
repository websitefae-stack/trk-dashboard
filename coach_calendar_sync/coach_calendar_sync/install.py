"""
Runs automatically when the app is installed via `bench install-app coach_calendar_sync`.
"""

import frappe


def after_install():
    from coach_calendar_sync.patches.install_custom_fields import execute as install_fields
    install_fields()

    # Create the singleton Settings document if it doesn't exist
    if not frappe.db.exists("Calendar Sync Settings", "Calendar Sync Settings"):
        frappe.new_doc("Calendar Sync Settings").insert(ignore_permissions=True)

    frappe.db.commit()
    print("coach_calendar_sync installed successfully.")
