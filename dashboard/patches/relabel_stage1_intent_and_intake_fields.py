"""
Stage 1's 4th and 5th milestones changed meaning (see leads.py's
sign_intent/submit_franchisee_intake, which now auto-tick these instead
of Ashley having to remember to do it by hand, and lead_details.js's
STAGE1_MILESTONES labels):

- stage1_intent_deposit_dbs_done/_date used to mean "Intent to Proceed +
  Deposit + DBS/Insurance Submitted" - now just "Intent to Proceed"
  (Deposit is still tracked manually by Ashley outside this system, and
  DBS/Insurance moved to its own milestone below).
- stage1_agreement_invoice_done/_date used to mean "Franchisee Agreement
  Signed + Final Invoice Paid" - now "Franchisee Intake + DBS/Insurance
  Submitted". The Agreement/Final Invoice step moved to the Client
  record itself, post-conversion (Franchise Onboarding section).

Relabels the underlying Custom Field records so Desk shows the same
wording as the dashboard - the fieldnames themselves are unchanged, so
no data is touched.
"""

import frappe

RELABELS = [
    ("Client Lead-stage1_intent_deposit_dbs_done", "Intent to Proceed"),
    ("Client Lead-stage1_intent_deposit_dbs_date", "Intent to Proceed Date"),
    ("Client Lead-stage1_agreement_invoice_done", "Franchisee Intake + DBS/Insurance Submitted"),
    ("Client Lead-stage1_agreement_invoice_date", "Franchisee Intake + DBS/Insurance Submitted Date"),
]


def execute():
    if not frappe.db.exists("DocType", "Client Lead"):
        return

    for custom_field_name, new_label in RELABELS:
        if frappe.db.exists("Custom Field", custom_field_name):
            frappe.db.set_value("Custom Field", custom_field_name, "label", new_label)

    frappe.clear_cache(doctype="Client Lead")
    frappe.db.commit()
