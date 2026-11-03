"""
One-off catch-up for the contact_details.py fix just shipped:
save_contact_for_scope only ever refreshed a Client's own cached
Client Contact Link.contact_name/email_id/phone when the save explicitly
named which Client to sync (linked_client) - the actual Contact Details
page, where contacts are normally edited, never sent that, so renaming
or re-emailing a Contact there left every Client file that links to it
still showing the old name/email/phone.

Re-syncs every Client Contact Link row's contact_name/email_id/phone
from its own linked Contact's current values, site-wide. Safe to run
more than once - only ever touches rows that are actually out of sync.
"""

import frappe

from dashboard.api.shared.contact_details import contact_display_name


def execute():
    if not frappe.db.exists("DocType", "Client Contact Link"):
        return

    rows = frappe.get_all(
        "Client Contact Link",
        filters={"parenttype": "Client"},
        fields=["name", "contact", "contact_name", "email_id", "phone"],
    )

    contact_names = {row.contact for row in rows if row.contact}
    if not contact_names:
        return

    contacts = {
        row.name: row
        for row in frappe.get_all(
            "Contact",
            filters={"name": ["in", list(contact_names)]},
            fields=["name", "full_name", "first_name", "last_name", "company_name", "email_id", "mobile_no"],
        )
    }

    updated = 0

    for row in rows:
        contact = contacts.get(row.contact)
        if not contact:
            continue

        new_contact_name = contact_display_name(contact)
        new_email = contact.get("email_id") or ""
        new_phone = contact.get("mobile_no") or ""

        if row.contact_name == new_contact_name and row.email_id == new_email and row.phone == new_phone:
            continue

        frappe.db.set_value(
            "Client Contact Link", row.name,
            {"contact_name": new_contact_name, "email_id": new_email, "phone": new_phone},
            update_modified=False,
        )
        updated += 1

    frappe.db.commit()
