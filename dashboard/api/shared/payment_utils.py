"""
Shared, single source of truth for turning a Sales Invoice into a
submitted Payment Entry. Used by both dashboard.py::mark_invoice_paid
(the dashboard home page's "Mark Paid" button) and
invoices.py::allocate_invoice_payment (the invoice details page's
payment button) - previously these were two independent hand-rolled
implementations that could drift out of sync with each other.

Every amount here is always kept to 2 decimal places - pounds and
pence - and never rounded to a whole pound.
"""

import frappe
from frappe import _
from frappe.utils import flt


def get_existing_payment_allocations(invoice_name):
    """
    Sum of allocated_amount across every SUBMITTED Payment Entry already
    referencing this invoice, read straight from Payment Entry Reference.
    This is the simplest, most directly-verifiable source of "how much has
    actually been paid" - unlike Payment Ledger Entry / GL Entry, whose
    amounts can be re-derived by the accounting layer at a different
    rounding precision than the Sales Invoice document's own 2-decimal-
    place fields.
    """
    result = frappe.db.sql(
        """
        select sum(per.allocated_amount) as amount
        from `tabPayment Entry Reference` per
        inner join `tabPayment Entry` pe on pe.name = per.parent
        where per.reference_doctype = 'Sales Invoice'
          and per.reference_name = %s
          and pe.docstatus = 1
        """,
        (invoice_name,),
        as_dict=True,
    )

    if result and result[0].get("amount") is not None:
        return flt(result[0]["amount"], 2)

    return 0.0


def get_payment_history(invoice_name):
    """
    Every SUBMITTED Payment Entry against this invoice, oldest first - the
    coach/franchisor-only "who paid what, when" quick view on the invoice
    details page. Sibling to get_existing_payment_allocations() (which
    only needs the sum); this returns the individual rows since an invoice
    can be paid off in several parts over time.
    """
    if not invoice_name:
        return []

    rows = frappe.db.sql(
        """
        select pe.name as payment_entry, pe.posting_date as posting_date,
               per.allocated_amount as amount, pe.reference_no as reference_no
        from `tabPayment Entry Reference` per
        inner join `tabPayment Entry` pe on pe.name = per.parent
        where per.reference_doctype = 'Sales Invoice'
          and per.reference_name = %s
          and pe.docstatus = 1
        order by pe.posting_date asc, pe.creation asc
        """,
        (invoice_name,),
        as_dict=True,
    )

    return [
        {
            "payment_entry": row.get("payment_entry"),
            "posting_date": str(row.get("posting_date") or ""),
            "amount": flt(row.get("amount"), 2),
            "reference_no": row.get("reference_no") or "",
        }
        for row in rows
    ]


def get_outstanding_amount_for_payment(cached_outstanding, grand_total, invoice_name):
    """
    Authoritative outstanding amount for payment purposes, always to 2dp -
    never rounded to a whole pound. Cross-checks the invoice's own cached
    outstanding_amount field against grand_total minus whatever has
    actually been allocated via submitted Payment Entries so far, and
    trusts whichever is lower (in case the cached field hasn't refreshed
    after some other, separate payment already reduced the true balance).
    """
    cached_outstanding = flt(cached_outstanding, 2)
    already_paid = get_existing_payment_allocations(invoice_name)

    if not already_paid:
        return cached_outstanding

    derived_outstanding = flt(flt(grand_total, 2) - already_paid, 2)

    return min(cached_outstanding, derived_outstanding)


def get_display_paid_amount(grand_total, outstanding_amount):
    """
    Sales Invoice.paid_amount is only ever kept in sync by ERPNext for POS
    invoices - every invoice this dashboard creates is settled by a
    Payment Entry reconciled against it instead (see
    build_and_submit_payment_entry() below), and that flow updates
    outstanding_amount but never touches paid_amount, leaving it at 0
    forever even once an invoice is fully paid. Derive the "paid" figure
    from the two fields ERPNext does keep in sync rather than trusting the
    stored field directly.
    """
    return flt(flt(grand_total, 2) - flt(outstanding_amount, 2), 2)


def build_and_submit_payment_entry(invoice_name, paid_to_account, payment_date, remarks, final_amount, reference_no=None):
    """
    Build the Payment Entry via ERPNext's own get_payment_entry() helper -
    the same code the standard Desk "Make Payment" button uses - for the
    party/account boilerplate, then explicitly set every amount field to
    our own 2dp-precise figure rather than trusting whatever internal
    default get_payment_entry() would otherwise compute. Also copies the
    invoice's own custom_bank_account/custom_client/custom_income_owner_coach
    onto the Payment Entry, so both callers of this helper get the same
    metadata instead of it depending on which code path created the payment.
    """
    from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

    final_amount = flt(final_amount, 2)
    invoice_doc = frappe.get_doc("Sales Invoice", invoice_name)

    payment_entry = get_payment_entry("Sales Invoice", invoice_name, bank_account=paid_to_account)
    payment_entry.posting_date = payment_date
    payment_entry.reference_date = payment_date
    payment_entry.reference_no = reference_no or f"Dashboard payment - {invoice_name}"
    payment_entry.remarks = remarks
    payment_entry.paid_amount = final_amount
    payment_entry.received_amount = final_amount

    for reference in payment_entry.references:
        if reference.reference_doctype == "Sales Invoice" and reference.reference_name == invoice_name:
            reference.allocated_amount = final_amount

    if payment_entry.meta.has_field("custom_bank_account") and invoice_doc.get("custom_bank_account"):
        payment_entry.custom_bank_account = invoice_doc.get("custom_bank_account")

    if payment_entry.meta.has_field("custom_client") and invoice_doc.get("custom_client"):
        payment_entry.custom_client = invoice_doc.get("custom_client")

    if payment_entry.meta.has_field("custom_income_owner_coach") and invoice_doc.get("custom_income_owner_coach"):
        payment_entry.custom_income_owner_coach = invoice_doc.get("custom_income_owner_coach")

    payment_entry.insert(ignore_permissions=True)
    payment_entry.submit()

    return payment_entry


def dump_gl_entries(voucher_no):
    return frappe.get_all(
        "GL Entry",
        filters={"voucher_type": "Sales Invoice", "voucher_no": voucher_no, "is_cancelled": 0},
        fields=[
            "account", "debit", "credit",
            "debit_in_account_currency", "credit_in_account_currency",
            "against_voucher_type", "against_voucher",
        ],
    )


def dump_payment_ledger_entries(voucher_no):
    if not frappe.db.exists("DocType", "Payment Ledger Entry"):
        return "Payment Ledger Entry doctype not found on this site."

    return frappe.get_all(
        "Payment Ledger Entry",
        filters={"voucher_type": "Sales Invoice", "voucher_no": voucher_no, "delinked": 0},
        fields=[
            "account", "amount", "amount_in_account_currency",
            "against_voucher_type", "against_voucher_no",
        ],
    )
