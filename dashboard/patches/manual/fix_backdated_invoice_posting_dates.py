import frappe

INVOICE_DATES = {
    "ACC-SINV-2026-00002": "2026-01-29",
    "ACC-SINV-2026-00003": "2026-01-21",
    "ACC-SINV-2026-00004": "2026-06-18",
    "ACC-SINV-2026-00005": "2026-01-13",
    "ACC-SINV-2026-00006": "2026-05-05",
    "ACC-SINV-2026-00007": "2025-12-09",
}


def execute():
    for invoice_name, new_date in INVOICE_DATES.items():
        if not frappe.db.exists("Sales Invoice", invoice_name):
            frappe.throw(f"Missing Sales Invoice: {invoice_name}")

        # Sales Invoice header
        frappe.db.set_value(
            "Sales Invoice",
            invoice_name,
            {
                "posting_date": new_date,
                "due_date": new_date,
            },
            update_modified=False,
        )

        # GL Entries created by this invoice
        frappe.db.sql(
            """
            update `tabGL Entry`
            set posting_date = %s
            where voucher_type = 'Sales Invoice'
              and voucher_no = %s
            """,
            (new_date, invoice_name),
        )

        # Payment Entry reference rows should carry the corrected invoice due date
        frappe.db.sql(
            """
            update `tabPayment Entry Reference`
            set due_date = %s
            where reference_doctype = 'Sales Invoice'
              and reference_name = %s
            """,
            (new_date, invoice_name),
        )

        # Your package docs, if they exist
        if frappe.db.exists("DocType", "Client Package"):
            frappe.db.sql(
                """
                update `tabClient Package`
                set posting_date = %s
                where sales_invoice = %s
                """,
                (new_date, invoice_name),
            )

    frappe.db.commit()
