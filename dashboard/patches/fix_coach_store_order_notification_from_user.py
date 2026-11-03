"""
One-off cleanup for the notifications.create_trk_notification bug just
fixed: every "<coach> placed a Coach Store order" notification meant for
a franchisor admin (ashley@/hq@/office@) was stamped from_user=<the
coach's own session>, which made it ALSO match the coach's own "see it
if you sent it" notification filter - confirmed live, a coach placing
one order saw their own confirmation plus 3 duplicate franchisor-admin
copies in their own notification list.

Corrects every already-created row of this kind by setting from_user
back to its own for_user (the admin it was actually meant for) - the
same fix the code now applies going forward (webshop_purchase.
_notify_coach_store_order passes from_user=admin_user explicitly).

Safe to run more than once - only ever touches rows where from_user is
still wrong.
"""

import frappe


def execute():
    if not frappe.db.exists("DocType", "Notification Log"):
        return

    meta = frappe.get_meta("Notification Log")
    if not meta.has_field("from_user") or not meta.has_field("for_user"):
        return

    rows = frappe.get_all(
        "Notification Log",
        filters={"email_content": ["like", "%placed a Coach Store order%"]},
        fields=["name", "for_user", "from_user"],
    )

    for row in rows:
        if row.for_user and row.from_user != row.for_user:
            frappe.db.set_value("Notification Log", row.name, "from_user", row.for_user, update_modified=False)

    frappe.db.commit()
