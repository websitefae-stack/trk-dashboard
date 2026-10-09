"""
Follow-up to create_recruitment_lead_doctype.py - same root cause
add_recruitment_lead_missing_contract_fields.py already had to fix once
for a specific subset (deposit invoice/franchisor signature/territory
map fields): that patch's own execute() only ever runs once, the very
first time "Recruitment Lead" gets created on a site
(frappe.db.exists(DOCTYPE_NAME): return), so any field added to its own
_fields() list AFTER that first deploy never actually reaches that
site's live schema.

Confirmed live again, this time against NDA/Intent/Contract signing
fields and the Franchisee Intake + DBS form: migrate_client_lead_to_
recruitment_lead copies fields across purely by name-matching against
the live target doctype's own meta (_copy_matching_fields) - any of
them missing there silently drops that data into an "unmapped fields"
note instead of landing on a real field, which is exactly what happened
to the two leads already migrated this way (Sam, Francesca) - their
submitted Franchisee Intake details and signing records never actually
reached their new Recruitment Lead record.

Rather than hand-listing yet another specific subset (this is now the
second time), this patch is comprehensive and self-maintaining instead:
re-reads create_recruitment_lead_doctype's own _fields() - the single
source of truth for this doctype's intended schema - and layers every
one of them on via create_custom_fields(), which is already safe to
call for a field that's already there (quietly skipped) regardless of
whether it's a plain DocField from the original create or an
already-applied Custom Field from an earlier patch like this one.
Existing data is untouched; this only ever adds columns.

Use resync_recruitment_lead_from_client_lead() (recruitment_leads.py)
afterwards to backfill any already-migrated lead whose data landed in
an "unmapped" note because a field it needed wasn't live yet.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from dashboard.patches.create_recruitment_lead_doctype import DOCTYPE_NAME, _fields


def execute():
    if not frappe.db.exists("DocType", DOCTYPE_NAME):
        # Nothing to repair - create_recruitment_lead_doctype's own
        # execute() creates it from scratch, already complete.
        return

    custom_fields = []
    previous_fieldname = None

    for field in _fields():
        field = dict(field)
        field.setdefault("module", "Dashboard")
        if previous_fieldname:
            field.setdefault("insert_after", previous_fieldname)
        custom_fields.append(field)
        previous_fieldname = field["fieldname"]

    create_custom_fields({DOCTYPE_NAME: custom_fields}, ignore_validate=True)
    frappe.db.commit()
