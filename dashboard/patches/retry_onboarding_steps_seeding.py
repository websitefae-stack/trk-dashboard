"""
ensure_onboarding_steps_seeded already "ran" as far as Frappe's patch
tracking is concerned - it caught its own exception (a
ModuleNotFoundError, since fixed in seed_onboarding_steps._seed())
and returned normally rather than letting it propagate, which is
exactly what it was designed to do so a bug here could never fail
migrate and roll back a whole deploy again. The side effect is that
fixing the underlying bug doesn't make it run again on its own - a
patch only ever runs once per site. This is a fresh patch, so it will.
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
        frappe.log_error(frappe.get_traceback(), "retry_onboarding_steps_seeding failed")
