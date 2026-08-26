"""
Root cause of every failed insert into Coach Onboarding Master Step,
finally identified from a real MySQL error surfaced through a manual
Data Import attempt: MySQLdb.OperationalError (4091, "Unknown
SEQUENCE: 'coach_onboarding_master_step_id_seq'").

autoname: autoincrement relies on a MariaDB SEQUENCE object that
Frappe normally creates automatically the first time a doctype's table
is built. This table was never "first built" for this doctype though -
it was Frappe's own core "Onboarding Step" table (a different naming
scheme entirely, since those records had names like "View Work Order
Summary Report", not autoincrement numbers), hijacked by the name
collision and later renamed. A metadata sync that changes autoname on
an existing table doesn't retroactively create the sequence a fresh
table creation would have - so it simply never existed, under either
name, this whole time. Every insert attempt (every patch here, and the
user's own manual Data Import) failed at the database level before
ever reaching the actual data.

Creates the missing sequence directly, then runs the same idempotent
seeding logic used everywhere else in this feature.
"""

import frappe

from dashboard.patches.seed_onboarding_steps import ONBOARDING_STEP_DOCTYPE, _seed

SEQUENCE_NAME = "coach_onboarding_master_step_id_seq"


def execute():
    if not frappe.db.exists("DocType", ONBOARDING_STEP_DOCTYPE):
        return

    try:
        frappe.db.sql(f"CREATE SEQUENCE IF NOT EXISTS `{SEQUENCE_NAME}`")
        frappe.db.commit()
    except Exception:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "create_missing_master_step_sequence failed")
        return

    try:
        _seed()
    except Exception:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "create_missing_master_step_sequence_and_seed - seeding failed")
