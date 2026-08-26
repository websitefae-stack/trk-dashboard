"""
Guarantees the 36 real Onboarding Journey steps exist, regardless of
whatever happened to the table before now (the core-doctype-name
collision, records mixed in from that, the cleanup/purge patches
written to untangle it). Rather than keep trying to reason about
exactly what state the data is in, this just re-asserts the correct
end state directly: re-runs the exact same idempotent seeding logic
from seed_onboarding_steps.py, which only ever inserts a step if one
with that exact step_name doesn't already exist - so this is a no-op
for anything already correct, and fills in anything missing.

Coaches who already have start_onboarding ticked but ended up with no
steps (or too few) don't need anything done for them directly here -
get_my_onboarding_steps and get_all_coaches_onboarding_progress both
already self-heal by re-provisioning any such coach automatically, the
next time either page is loaded, once the real step list this patch
guarantees is in place.
"""

import frappe

from dashboard.patches.seed_onboarding_steps import ONBOARDING_STEP_DOCTYPE, _seed


def execute():
    if not frappe.db.exists("DocType", ONBOARDING_STEP_DOCTYPE):
        return

    try:
        _seed()
    except Exception:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "ensure_onboarding_steps_seeded failed")
