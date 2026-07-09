"""
Regression coverage for the pence-vs-whole-pound payment bug: invoice
amounts must never be treated as rounded to the nearest whole pound
anywhere in the dashboard's payment flow. Run with:

    bench --site <site> run-tests --app dashboard --module dashboard.tests.test_invoice_payment_rounding
"""

from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from dashboard.api.shared.dashboard import _get_outstanding_amount_for_payment


class TestInvoicePaymentRounding(FrappeTestCase):
    def test_outstanding_amount_is_never_rounded_to_a_whole_pound(self):
        # A fresh, fully-unpaid invoice's outstanding amount must match its
        # grand_total to the penny, for any decimal total - not just ones
        # that happen to be whole pounds.
        for amount in (439.20, 120.40, 70.26):
            with self.subTest(amount=amount):
                outstanding = _get_outstanding_amount_for_payment(
                    cached_outstanding=amount,
                    grand_total=amount,
                    invoice_name="TEST-INVOICE-DOES-NOT-EXIST",
                )
                self.assertEqual(flt(outstanding, 2), flt(amount, 2))

    def test_outstanding_amount_accounts_for_existing_partial_allocations(self):
        # Sanity check on the fallback path itself: with no existing
        # Payment Entry allocations (the common case), the cached
        # outstanding_amount is trusted as-is, to 2dp.
        outstanding = _get_outstanding_amount_for_payment(
            cached_outstanding=70.26,
            grand_total=70.26,
            invoice_name="TEST-INVOICE-DOES-NOT-EXIST",
        )
        self.assertEqual(outstanding, 70.26)
