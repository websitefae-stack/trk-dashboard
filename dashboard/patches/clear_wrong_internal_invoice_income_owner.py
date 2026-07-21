"""
One-time cleanup for _set_invoice_defaults()'s custom_income_owner_coach
fix: any invoice raised against a Coach's own linked_client (e.g. a
Franchise Fee) before that fix had custom_income_owner_coach wrongly
defaulted to the primary_coach of that Client record - which, for a
coach's own internal billing record, is that same coach. The franchisor's
Outstanding Internal Invoices section treats any invoice with
custom_income_owner_coach set as another coach's private business rather
than office's, so these were silently hidden from HQ's oversight view even
though they're perfectly ordinary office-to-coach invoices.

Clears custom_income_owner_coach on any already-existing invoice where it
was set to the same coach whose own linked_client the invoice is against -
never touches one where it's set to a *different* coach (a genuine
bank-account-override case, e.g. Emily invoicing on SJ's behalf, which is
exactly the "someone else's private business" case that field exists for).

Runs automatically on the next `bench migrate` (part of a normal deploy) -
no manual step needed.
"""

import frappe


def clear_wrong_internal_invoice_income_owner():
    if not frappe.db.exists("DocType", "Coach") or not frappe.db.exists("DocType", "Sales Invoice"):
        return

    coach_meta = frappe.get_meta("Coach")
    invoice_meta = frappe.get_meta("Sales Invoice")

    if not coach_meta.has_field("linked_client") or not invoice_meta.has_field("custom_income_owner_coach"):
        return

    coach_rows = frappe.get_all(
        "Coach",
        filters={"linked_client": ["is", "set"]},
        fields=["name", "linked_client"],
    )

    for row in coach_rows:
        if not row.linked_client:
            continue

        invoice_names = frappe.get_all(
            "Sales Invoice",
            filters={
                "custom_client": row.linked_client,
                "custom_income_owner_coach": row.name,
            },
            pluck="name",
        )

        for name in invoice_names:
            try:
                frappe.db.set_value(
                    "Sales Invoice", name, "custom_income_owner_coach", "", update_modified=False
                )
            except Exception:
                frappe.log_error(frappe.get_traceback(), f"Clear Internal Invoice Income Owner - {name}")

    frappe.db.commit()


def execute():
    clear_wrong_internal_invoice_income_owner()
