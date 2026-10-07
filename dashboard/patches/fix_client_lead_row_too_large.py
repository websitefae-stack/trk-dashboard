"""
Fixes a live migration failure: add_franchise_lead_contract_fields.py's
ALTER TABLE failed with MySQL/MariaDB error 1118 ("Row size too
large... You have to change some columns to TEXT or BLOBs").
`tabClient Lead` has accumulated a very large number of custom fields
across many patches over time (NDA, Intent to Proceed, Franchisee
Intake, Safer Recruitment Checklist, Stage 1, now the Franchise
Agreement fields), and finally crossed InnoDB's 65,535-byte inline
row-size limit.

The real fix is ROW_FORMAT=DYNAMIC - MariaDB/InnoDB's own suggested
remedy. With DYNAMIC, a TEXT/MEDIUMTEXT/LONGTEXT column (this table has
several - the signed NDA/Intent/Franchise Agreement snapshots, Safer
Recruitment outstanding actions, etc) is stored off-page and only costs
~20 bytes toward that inline limit, instead of up to 768 bytes under
the older COMPACT/REDUNDANT format this table was apparently still
using (newer tables default to DYNAMIC automatically; this one
predates that, or was created before Frappe/MariaDB switched the
default). A one-off ALTER TABLE, not something create_custom_fields
itself can do - it only adds columns, it never changes row format.

Idempotent (re-running on an already-DYNAMIC table is a harmless
no-op) - runs BEFORE add_franchise_lead_contract_fields in patches.txt
so that patch's own ALTER TABLE (which failed) can succeed on retry
once this one has already freed up the row's available budget.
"""

import frappe


def execute():
    if not frappe.db.exists("DocType", "Client Lead"):
        return

    frappe.db.sql_ddl("ALTER TABLE `tabClient Lead` ROW_FORMAT=DYNAMIC")
    frappe.db.commit()
