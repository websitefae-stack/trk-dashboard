"""
Adds "Start Onboarding" (+ its own "Onboarding Started On" timestamp) to
Coach - the opt-in trigger for the Coach Onboarding Journey. Deliberately
opt-in and per coach: ticking this is what provisions that one coach's
Coach Onboarding Step rows (see onboarding.provision_onboarding_steps,
hooked on Coach.on_update) - existing coaches are never affected just by
this field existing, since it defaults unticked and nothing provisions
retroactively.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

COACH_FIELDS = [
    {
        "fieldname": "start_onboarding",
        "fieldtype": "Check",
        "label": "Start Onboarding",
        "description": (
            "Tick once this coach's Frappe access is set up and they're ready to begin the Onboarding "
            "Journey (typically the day of, or the day before, their Training Day) - this creates their "
            "onboarding steps. Existing coaches are never affected by leaving this unticked."
        ),
        "insert_after": "linked_client",
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
]


def execute():
    if not frappe.db.exists("DocType", "Coach"):
        return

    create_custom_fields({"Coach": COACH_FIELDS}, ignore_validate=True)
    frappe.db.commit()
