"""
One-time backfill for invoices emailed before custom_invoice_sent_on
existed (add_invoice_sent_on_field.py) - a separate patch so it still
runs even though that one may already have executed on a prior deploy,
which would otherwise skip re-running it.

send_invoice_email() (invoices.py) has always called
frappe.sendmail(reference_doctype="Sales Invoice", reference_name=...),
which creates a Communication record for every email it sends - that
history already exists and doesn't need to be lost just because the
field to show it didn't. Uses the most recent Communication per invoice.

Runs automatically on the next `bench migrate` (part of a normal deploy) -
no manual step needed.
"""

import frappe


def execute():
    if not frappe.db.exists("DocType", "Sales Invoice"):
        return

    if not frappe.get_meta("Sales Invoice").has_field("custom_invoice_sent_on"):
        return

    rows = frappe.get_all(
        "Communication",
        filters={
            "reference_doctype": "Sales Invoice",
            "communication_type": "Communication",
            "sent_or_received": "Sent",
        },
        fields=["reference_name", "creation"],
        order_by="creation asc",
    )

    # Iterating oldest-first and overwriting means each invoice ends up with
    # its most recent send - the same "latest wins" rule
    # send_invoice_email() itself follows going forward.
    latest_sent_on = {}
    for row in rows:
        if row.reference_name:
            latest_sent_on[row.reference_name] = row.creation

    for invoice_name, sent_on in latest_sent_on.items():
        if not frappe.db.exists("Sales Invoice", invoice_name):
            continue

        try:
            frappe.db.set_value(
                "Sales Invoice", invoice_name, "custom_invoice_sent_on", sent_on, update_modified=False
            )
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Backfill Invoice Sent On - {invoice_name}")

    frappe.db.commit()
