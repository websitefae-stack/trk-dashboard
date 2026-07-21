"""
Both earlier cleanup patches only cleared custom_income_owner_coach when
it was set to the same coach as the one being invoiced - that was based on
what the client_primary/bank-account fallback logic in
_set_invoice_header_fields() could produce. It turned out the actual value
sitting on every affected invoice was "The Resilient Office" - a fixed
placeholder that field's own default value applies before that code ever
runs, not anything either fallback would have produced - so neither
earlier patch ever matched it and cleared nothing.

An internal invoice (against a coach's own linked_client) always belongs
to HQ, full stop, so this clears custom_income_owner_coach unconditionally
for every invoice against every coach's linked_client, whatever value is
currently sitting there - not just a specific one.

Runs automatically on the next `bench migrate` (part of a normal deploy) -
no manual step needed.
"""

import frappe


def execute():
    if not frappe.db.exists("DocType", "Coach") or not frappe.db.exists("DocType", "Sales Invoice"):
        return

    coach_meta = frappe.get_meta("Coach")
    invoice_meta = frappe.get_meta("Sales Invoice")

    if not coach_meta.has_field("linked_client") or not invoice_meta.has_field("custom_income_owner_coach"):
        return

    linked_client_names = frappe.get_all(
        "Coach",
        filters={"linked_client": ["is", "set"]},
        pluck="linked_client",
    )

    if not linked_client_names:
        return

    invoice_names = frappe.get_all(
        "Sales Invoice",
        filters={
            "custom_client": ["in", linked_client_names],
            "custom_income_owner_coach": ["is", "set"],
        },
        pluck="name",
    )

    for name in invoice_names:
        try:
            frappe.db.set_value(
                "Sales Invoice", name, "custom_income_owner_coach", "", update_modified=False
            )
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Clear Internal Invoice Income Owner v3 - {name}")

    frappe.db.commit()
