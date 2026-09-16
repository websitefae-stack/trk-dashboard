"""
Creation of Rachel's Store Manager login (store@theresilienthub.co.uk) -
lands her on /store_db instead of the franchisor/coach dashboards.

Creates the User if it doesn't already exist (send_welcome_email=1, so
Frappe's own invite email handles setting a password - nothing here ever
sets or knows a password), then links it via a Store Manager record.

NOT a patches.txt entry despite living in patches/ and being named like
one - v2 because the original create_store_manager_for_rachel WAS a
patches.txt patch, shipped in the same deploy as the Store Manager
doctype itself. patches.txt entries run before doctype/schema sync by
default, so it always found "Store Manager" missing, no-opped via the
guard below, and got marked done anyway (Frappe never retries a patch
once logged, even a no-op). A "[post_model_sync]" section header was
tried next to force it to run after sync instead, but this site's
Frappe version doesn't actually support that patches.txt syntax
(AppNotInstalledError: App [post_model_sync] is not installed).

execute() is instead wired up as this app's after_migrate hook (see
hooks.py) - that runs once at the very end of `bench migrate`, after
every patch and every doctype sync, so it's guaranteed to see "Store
Manager" already existing without depending on patches.txt section
syntax at all. Runs on every migrate, not just once, so it stays
idempotent via the guards below.
"""

import frappe

STORE_MANAGER_EMAIL = "store@theresilienthub.co.uk"
STORE_MANAGER_FULL_NAME = "Rachel"


def execute():
    if not frappe.db.exists("DocType", "Store Manager"):
        return

    if not frappe.db.exists("User", STORE_MANAGER_EMAIL):
        user = frappe.new_doc("User")
        user.email = STORE_MANAGER_EMAIL
        user.first_name = STORE_MANAGER_FULL_NAME
        user.user_type = "Website User"
        user.enabled = 1
        user.send_welcome_email = 1
        user.insert(ignore_permissions=True)

    if not frappe.db.exists("Store Manager", {"user": STORE_MANAGER_EMAIL}):
        manager = frappe.new_doc("Store Manager")
        manager.user = STORE_MANAGER_EMAIL
        manager.full_name = STORE_MANAGER_FULL_NAME
        manager.email = STORE_MANAGER_EMAIL
        manager.enabled = 1
        manager.insert(ignore_permissions=True)

    frappe.db.commit()
