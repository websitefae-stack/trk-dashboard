"""
Coach Onboarding Step rows created while _create_coach_onboarding_steps
relied on fetch_from (see api/shared/onboarding.py) came out with
step_name/stage/owner_type/etc. blank - fetch_from didn't reliably
populate them on insert. That function now copies the values across
explicitly instead, but this backfills any rows that were already
created blank before that fix, by copying straight from each row's
linked Onboarding Step.
"""

import frappe

COACH_STEP_DOCTYPE = "Coach Onboarding Step"
STEP_DOCTYPE = "Coach Onboarding Master Step"

COPY_FIELDS = [
    ("step_name", "step_name"),
    ("stage", "stage"),
    ("owner_type", "owner_type"),
    ("stage_sort_order", "stage_sort_order"),
    ("sort_order", "sort_order"),
    ("expected_result", "expected_result"),
    ("where_it_happens", "where_it_happens"),
    ("link_url", "link_url"),
    ("depends_on", "depends_on_step"),
]


def execute():
    if not frappe.db.exists("DocType", COACH_STEP_DOCTYPE) or not frappe.db.exists("DocType", STEP_DOCTYPE):
        return

    rows = frappe.get_all(COACH_STEP_DOCTYPE, fields=["name", "onboarding_step", "step_name"])
    blank_rows = [row for row in rows if row.onboarding_step and not row.step_name]

    if not blank_rows:
        return

    for row in blank_rows:
        master = frappe.db.get_value(
            STEP_DOCTYPE,
            row.onboarding_step,
            [source for source, _target in COPY_FIELDS],
            as_dict=True,
        )
        if not master:
            continue

        updates = {target: master.get(source) for source, target in COPY_FIELDS}
        frappe.db.set_value(COACH_STEP_DOCTYPE, row.name, updates, update_modified=False)

    frappe.db.commit()
