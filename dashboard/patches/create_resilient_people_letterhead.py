"""
A dedicated Letter Head for online Store/course sales - Ashley's own
call: any merch or course purchase (guest checkout, or a coach's own
Coach Store order) should always be invoiced under The Resilient People
branding, regardless of which of the five brand sites the actual item
was bought through, and should show HQ's own banking details rather
than whichever Company happens to be set on the invoice.

Deliberately a brand-new, separate Letter Head record rather than
editing the existing "Resilient Kid" one that every other invoice type
(coaching sessions, statements) already uses and whose Jinja branches
per-client (Kid/Teen/People/School/Franchise) - that content lives only
in the database, was never authored by this codebase, and safely
extending it without being able to read its current logic isn't
possible from here. This one is entirely self-contained instead:

- Header: The Resilient People logo + the same office address/contact
  details already shown on every other invoice.
- Footer: banking details read live from Webshop Payment Settings'
  own `bank_account` (the exact account Stripe payments are already
  recorded against - see webshop_purchase.py's _get_bank_account_gl_
  account) rather than hardcoded here, so it can never drift out of
  sync with whichever account actually gets paid into. Also shows
  "Paid via Stripe" when the invoice carries a custom_stripe_session_id
  (see add_online_client_to_sales_invoice.py) - blank for anything
  invoiced this way that wasn't actually a Stripe payment (e.g. a Coach
  Store order, paid by the coach separately).

Safe to run more than once - only ever creates the record if it
doesn't already exist; never overwrites anything Ashley edits into it
afterwards via Desk.
"""

import frappe

LETTERHEAD_NAME = "Resilient People"

HEADER_HTML = """
<div style="display:flex; align-items:flex-start; justify-content:space-between; font-family:Arial, Helvetica, sans-serif;">
  <div>
    <img src="https://theresilienthub.co.uk/files/TRPeople_Wordmark_Logo.png" style="height:60px;">
  </div>
  <div style="text-align:right; font-size:11px; line-height:1.6; color:#222;">
    <div style="font-weight:700; font-size:13px;">The Resilient People</div>
    <div>Fox Corner, Chester Road</div>
    <div>Hartford</div>
    <div>Chester CW8 1LL, United Kingdom</div>
    <div>Website: https://theresilientkid.co.uk</div>
    <div>Email: ashley@theresilientkid.co.uk</div>
    <div>Contact: +44 7482 787818</div>
  </div>
</div>
""".strip()

FOOTER_HTML = """
<div style="font-size:11px; font-family:Arial, Helvetica, sans-serif; color:#222; border-top:1px solid #ccc; padding-top:8px;">
{% set bank_account_name = frappe.db.get_single_value("Webshop Payment Settings", "bank_account") %}
{% set bank = frappe.db.get_value("Bank Account", bank_account_name, ["bank", "account_name", "bank_account_no", "branch_code"], as_dict=True) if bank_account_name else None %}
{% if bank %}
<strong>Banking Details</strong><br>
Bank Name: {{ bank.bank or "" }}<br>
Account Name: {{ bank.account_name or "" }}<br>
Account Number: {{ bank.bank_account_no or "" }}<br>
Branch Code: {{ bank.branch_code or "" }}<br>
{% endif %}
{% if doc and doc.get("custom_stripe_session_id") %}
<p style="margin-top:8px;"><strong>Paid via Stripe</strong></p>
{% endif %}
</div>
""".strip()


def execute():
    if not frappe.db.exists("DocType", "Letter Head"):
        return

    if frappe.db.exists("Letter Head", LETTERHEAD_NAME):
        return

    doc = frappe.new_doc("Letter Head")
    doc.letter_head_name = LETTERHEAD_NAME
    doc.source = "HTML"
    doc.content = HEADER_HTML
    doc.footer = FOOTER_HTML
    doc.disabled = 0
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
