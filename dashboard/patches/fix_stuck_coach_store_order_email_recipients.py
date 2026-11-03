"""
One-off cleanup for every Coach Store order confirmation email stuck
retrying (and failing) forever with "Bad recipient address syntax" -
confirmed live, 3 separate invoices (ACC-SINV-2026-00480/00481/00482)
sitting in Email Queue with status Error, generating a repeating Error
Log entry every time Frappe's scheduled frappe.email.queue.flush job
retries them.

The underlying bug (_send_coach_order_confirmation_email passing
office_notification_email - "ashley@..., store@..." - as a single cc
entry instead of splitting it) is already fixed going forward, but any
email already queued before that fix has the malformed value baked
into its own Email Queue Recipient row, which the code fix can't touch
retroactively.

Corrects each stuck row to just the first address it actually contains
- splitting it into a proper second recipient row instead risks
re-sending an already-stale order notification a second time, days
late, for no real benefit. The next flush then succeeds instead of
failing again.

Safe to run more than once.
"""

import re

import frappe


def execute():
    if not frappe.db.exists("DocType", "Email Queue Recipient"):
        return

    recipient_meta = frappe.get_meta("Email Queue Recipient")
    has_status = recipient_meta.has_field("status")

    rows = frappe.get_all(
        "Email Queue Recipient",
        or_filters=[["recipient", "like", "%,%"], ["recipient", "like", "%;%"]],
        fields=["name", "parent", "recipient"],
    )

    fixed_parents = set()

    for row in rows:
        addresses = [a.strip() for a in re.split(r"[,;]", row.recipient or "") if a.strip()]
        if len(addresses) <= 1:
            continue

        updates = {"recipient": addresses[0]}
        if has_status:
            updates["status"] = "Not Sent"

        frappe.db.set_value("Email Queue Recipient", row.name, updates)
        fixed_parents.add(row.parent)

    # Put each affected Email Queue back to Not Sent so the next
    # scheduled flush actually retries it promptly with the now-valid
    # recipient, rather than waiting on whatever Error-status backoff
    # already applied.
    for parent in fixed_parents:
        if frappe.db.exists("Email Queue", parent):
            frappe.db.set_value("Email Queue", parent, "status", "Not Sent")

    frappe.db.commit()
