"""
Practice Document, Coach Document Requirement and Client Document Share all
have naming_rule "Autoincrement", which on MariaDB relies on a SEQUENCE
object (e.g. practice_document_id_seq) rather than a plain AUTO_INCREMENT
column. Frappe normally creates that sequence the first time a doctype's
table is created with this naming rule - but all three tables went through
several drop/recreate cycles earlier (see the JSON schema rebuild after
they were accidentally dropped), and at least one of those cycles left the
tables in place without ever running the sequence creation step, so every
insert fails with e.g. "Unknown SEQUENCE: 'practice_document_id_seq'".
This creates the sequences directly, idempotently, so re-running this
patch (or migrating again) is always safe.
"""

import frappe

DOCTYPES = ["Practice Document", "Coach Document Requirement", "Client Document Share"]


def execute():
    if frappe.db.db_type != "mariadb":
        return

    for doctype in DOCTYPES:
        if not frappe.db.exists("DocType", doctype):
            continue

        sequence_name = frappe.scrub(doctype) + "_id_seq"
        frappe.db.sql(f"CREATE SEQUENCE IF NOT EXISTS {sequence_name}")

    frappe.db.commit()
