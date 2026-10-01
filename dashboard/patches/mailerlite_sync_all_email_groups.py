"""
Ashley wants every Frappe Email Group (newsletter subscribers, course
sign-ups, website customers, etc.) merged into the one MailerLite
Group ID on MailerLite Settings, not just a single hand-picked group -
see mailerlite_sync.py, which no longer restricts syncing to
settings.synced_email_group. Removes that now-unused field (and its
Section Break) from the existing Single doctype; create_mailerlite_
settings.py only runs once (its own `if frappe.db.exists(...): return`
guard), so an already-live site needs this separate patch to drop the
field rather than relying on the original patch being re-run.
"""

import frappe

DOCTYPE_NAME = "MailerLite Settings"
FIELDS_TO_REMOVE = ["sync_section", "synced_email_group"]


def execute():
    if not frappe.db.exists("DocType", DOCTYPE_NAME):
        return

    doc = frappe.get_doc("DocType", DOCTYPE_NAME)
    remaining = [f for f in doc.fields if f.fieldname not in FIELDS_TO_REMOVE]

    if len(remaining) == len(doc.fields):
        return

    doc.fields = remaining
    doc.save(ignore_permissions=True)
    frappe.db.commit()
