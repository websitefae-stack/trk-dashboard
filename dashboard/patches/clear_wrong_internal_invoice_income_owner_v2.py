"""
Re-runs clear_wrong_internal_invoice_income_owner()'s cleanup under a new
patch name, guaranteed to execute on the next `bench migrate` regardless of
whether the original patch already ran on this site.

That first fix only covered custom_income_owner_coach being wrongly
defaulted from the invoiced Client's primary_coach - a second, identical
bug existed via the bank-account-override path (an internal invoice's bank
account naturally defaults to that same coach's own account, which was
being read as "this coach owns the income" the same way an actual override
to a *different* coach's account would). Both defaults are fixed now, but
any invoice created or resaved between the first patch running and this
fix landing would have been set wrong again via that second path - this
clears it a second time to catch those too.

Runs automatically on the next `bench migrate` (part of a normal deploy) -
no manual step needed.
"""

from dashboard.patches.clear_wrong_internal_invoice_income_owner import (
    clear_wrong_internal_invoice_income_owner,
)


def execute():
    clear_wrong_internal_invoice_income_owner()
