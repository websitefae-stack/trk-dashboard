"""
One-time cleanup for Email Queue rows already stuck with the "Sender
address rejected: not owned by user ..." SMTP failure - see
email_queue_fixes.py's module docstring for the full story. The
before_insert hook added alongside this patch stops any NEW row from
ever being created this way, but it can't touch rows that were already
written before that hook existed - those would otherwise just keep
retrying and failing forever. Reuses the exact same fix, applied once
to whatever's already sitting broken in the queue.
"""

import frappe

from dashboard.api.shared.email_queue_fixes import fix_spoofed_relay_sender


def execute():
    if not frappe.db.exists("DocType", "Email Queue"):
        return

    stuck_names = frappe.get_all(
        "Email Queue",
        filters={"status": ["in", ["Not Sent", "Error"]]},
        pluck="name",
    )

    for name in stuck_names:
        doc = frappe.get_doc("Email Queue", name)
        original_sender = doc.sender

        fix_spoofed_relay_sender(doc)

        if doc.sender != original_sender:
            frappe.db.set_value(
                "Email Queue", name, {"sender": doc.sender, "message": doc.message}, update_modified=False
            )

    frappe.db.commit()
