"""
One-time creation of Rachel's Store Manager login (store@theresilienthub.
co.uk) - lands her on /store_db instead of the franchisor/coach dashboards.

Creates the User if it doesn't already exist (send_welcome_email=1, so
Frappe's own invite email handles setting a password - nothing here ever
sets or knows a password), then links it via a Store Manager record.

v2 because the original create_store_manager_for_rachel patch shipped in
the same deploy as the Store Manager doctype itself - patches.txt entries
run before doctype/schema sync by default, so it always found "Store
Manager" missing, no-opped via the guard below, and got marked done
anyway (Frappe never retries a patch once logged, even a no-op). Listed
under [post_model_sync] this time so it actually runs after the doctype
exists. The guard stays, since a fresh site could still reach this before
sync for some other reason.

Runs automatically on the next `bench migrate`. Safe to run more than
once - skips whichever half already exists.
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
