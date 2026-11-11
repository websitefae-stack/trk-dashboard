"""
Adds "Start Onboarding" (+ "Onboarding Started On" and "Training Day
Completed On") to Session Worker - the same opt-in trigger Coach has
(see add_coach_start_onboarding_field.py), extended here now that the
Onboarding Journey covers Session Workers too (see onboarding.py's
Session Worker provisioning, and Coach Onboarding Master Step's new
Applies To field).

training_day_completed_on is read generically by permissions.py's
get_expired_legal_items/_effective_missing_since and legal_expiry_
reminders.py already - both already call doc.get("training_day_
completed_on") on whichever profile doc (Coach or Session Worker) they
were handed, rather than assuming Coach specifically. Adding the same
field to Session Worker is the only change needed for the missing-
document grace period to wait for a session worker's own Training Day
too, exactly like it already does for coaches.

Session Worker is a core doctype this app doesn't own the JSON for, so
new fields always go through create_custom_fields - same pattern as
every other Session Worker field this app has added. Unlike the
Identification/Safeguarding Certificate fields, none of these are a
Table field pointing at a doctype introduced in this same deploy, so
there's no doctype-sync ordering trap here - this is a plain
patches.txt entry, not after_migrate.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

SESSION_WORKER_FIELDS = [
    {
        "fieldname": "start_onboarding",
        "fieldtype": "Check",
        "label": "Start Onboarding",
        "description": (
            "Tick once this session worker's Frappe access is set up and they're ready to begin "
            "the Onboarding Journey - this creates their onboarding steps. Existing session "
            "workers are never affected by leaving this unticked."
        ),
        "insert_after": "safeguarding_certificate_missing_since",
        "module": "Dashboard",
    },
    {
        "fieldname": "onboarding_started_on",
        "fieldtype": "Datetime",
        "label": "Onboarding Started On",
        "read_only": 1,
        "insert_after": "start_onboarding",
        "module": "Dashboard",
    },
    {
        "fieldname": "training_day_completed_on",
        "fieldtype": "Date",
        "label": "Training Day Completed On",
        "read_only": 1,
        "insert_after": "onboarding_started_on",
        "module": "Dashboard",
    },
]


def execute():
    if not frappe.db.exists("DocType", "Session Worker"):
        return

    create_custom_fields({"Session Worker": SESSION_WORKER_FIELDS}, ignore_validate=True)
    frappe.db.commit()
