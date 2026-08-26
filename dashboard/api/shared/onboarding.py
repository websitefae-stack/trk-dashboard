"""
Coach Onboarding Journey - Tier 1.

Two doctypes: "Onboarding Step" is the master template (managed directly in
the Frappe Desk by HQ, same pattern as Practice Document), and "Coach
Onboarding Step" is one row per coach per step, created only once - when
that coach's own "Start Onboarding" checkbox is ticked (see
provision_onboarding_steps, hooked on Coach.on_update). This is
deliberately opt-in and per coach: existing coaches are never affected,
since nothing here runs unless that field is explicitly ticked.

A step whose Onboarding Step has a "Depends On" set shows as locked (not
yet actionable) for a coach until the step it depends on is Done - see
_is_locked below. This is the "only show now and next" behaviour from the
onboarding journey design, not a hard database-level gate.
"""

import frappe
from frappe import _
from frappe.utils import now_datetime

from dashboard.api.shared.permissions import ensure_logged_in, is_franchisor_user, get_current_coach_name
from dashboard.api.shared.utils import coalesce_str

COACH_ONBOARDING_STEP_DOCTYPE = "Coach Onboarding Step"
# Deliberately NOT "Onboarding Step" - that name collides with a doctype
# Frappe's own core framework already ships (used for ERPNext's built-in
# "Getting Started" setup guidance). Creating a doctype with that same
# name overwrote the core one's schema, which is why this is prefixed.
ONBOARDING_STEP_DOCTYPE = "Coach Onboarding Master Step"

COACH_STEP_FIELDS = [
    "name", "onboarding_step", "step_name", "stage", "owner_type", "status",
    "expected_result", "where_it_happens", "link_url", "depends_on_step",
    "stage_sort_order", "sort_order", "completed_on", "completed_by", "notes",
]


def provision_onboarding_steps(doc, method=None):
    """
    Coach.on_update hook. Fires on every Coach save, but only actually
    does anything the one time start_onboarding flips from unticked to
    ticked - and only if this coach doesn't already have onboarding rows,
    so re-saving the Coach record afterwards is always a no-op here.
    """
    if not doc.get("start_onboarding"):
        return

    if not doc.has_value_changed("start_onboarding"):
        return

    if frappe.db.exists(COACH_ONBOARDING_STEP_DOCTYPE, {"coach": doc.name}):
        return

    try:
        _create_coach_onboarding_steps(doc.name)
        frappe.db.set_value("Coach", doc.name, "onboarding_started_on", now_datetime(), update_modified=False)
        frappe.db.commit()
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Onboarding Provisioning Failed - {doc.name}")


def _create_coach_onboarding_steps(coach_name):
    # Field values are copied across explicitly here rather than relying
    # on the doctype's fetch_from configuration - fetch_from is meant to
    # do this automatically on insert, but proved unreliable in practice
    # (rows came out with step_name/stage/etc. blank), so this doesn't
    # depend on it working. It also matches what the field descriptions
    # already say is intended: a copy taken at creation time, not a live
    # link that would rewrite a coach's history if the master step is
    # edited later.
    # is_active alone isn't a safe filter here: this table used to be
    # shared with a Frappe core doctype of the same name (see the
    # rename patch) - when is_active was added as a new field with a
    # default of 1, MySQL backfills that default onto every pre-existing
    # row too, including all the leftover core-Frappe ones. Also
    # requiring stage to be set is what actually distinguishes this
    # app's real steps, since stage is a field only this app's records
    # have ever had a value in.
    steps = frappe.get_all(
        ONBOARDING_STEP_DOCTYPE,
        filters=[["is_active", "=", 1], ["stage", "is", "set"]],
        fields=[
            "name", "step_name", "stage", "owner_type", "stage_sort_order",
            "sort_order", "expected_result", "where_it_happens", "link_url", "depends_on",
        ],
        order_by="stage_sort_order asc, sort_order asc",
    )

    for step in steps:
        frappe.get_doc({
            "doctype": COACH_ONBOARDING_STEP_DOCTYPE,
            "coach": coach_name,
            "onboarding_step": step.name,
            "status": "Not Started",
            "step_name": step.step_name,
            "stage": step.stage,
            "owner_type": step.owner_type,
            "stage_sort_order": step.stage_sort_order,
            "sort_order": step.sort_order,
            "expected_result": step.expected_result,
            "where_it_happens": step.where_it_happens,
            "link_url": step.link_url,
            "depends_on_step": step.depends_on,
        }).insert(ignore_permissions=True)


def _resolve_target_coach(coach=None):
    """
    Whose onboarding is being read/acted on: an explicit coach param is
    only ever honoured for a franchisor (HQ looking at one coach's
    checklist from their overview) - anyone else always gets their own,
    regardless of what's passed.
    """
    ensure_logged_in()

    coach = coalesce_str("coach", coach)

    if coach and is_franchisor_user():
        if not frappe.db.exists("Coach", coach):
            frappe.throw(_("Coach not found."))
        return coach

    own_coach_name = get_current_coach_name(optional=True)

    if not own_coach_name:
        frappe.throw(_("No Coach profile is linked to your user."), frappe.PermissionError)

    return own_coach_name


_STEP_COPY_FIELDS = [
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


def _repair_blank_rows(rows):
    """
    Coach Onboarding Step rows can end up with their copied step details
    blank (the fetch_from that used to populate them on insert wasn't
    reliable - see _create_coach_onboarding_steps). Rather than trust a
    one-off backfill patch to have caught every case, every read here
    self-heals: any row missing its step_name gets re-copied from its
    linked Onboarding Step on the spot, both for this response and
    written back to the row itself so the Desk list view is correct too
    (and this never has to run again for that row).
    """
    blank_rows = [row for row in rows if row.onboarding_step and (not row.step_name or not row.stage)]
    if not blank_rows:
        return

    step_names = list({row.onboarding_step for row in blank_rows})
    masters = frappe.get_all(
        ONBOARDING_STEP_DOCTYPE,
        filters={"name": ["in", step_names]},
        fields=["name"] + [source for source, _target in _STEP_COPY_FIELDS],
    )
    master_by_name = {master.name: master for master in masters}

    for row in blank_rows:
        master = master_by_name.get(row.onboarding_step)
        if not master:
            continue

        updates = {}
        for source, target in _STEP_COPY_FIELDS:
            value = master.get(source)
            row[target] = value
            updates[target] = value

        frappe.db.set_value(COACH_ONBOARDING_STEP_DOCTYPE, row.name, updates, update_modified=False)

    frappe.db.commit()


def _is_locked(row, done_step_names):
    return bool(row.depends_on_step) and row.depends_on_step not in done_step_names and row.status != "Done"


def _group_by_stage(rows):
    done_step_names = {row.onboarding_step for row in rows if row.status == "Done"}

    stages = []
    stage_index = {}

    for row in rows:
        # If step_name is still blank after _repair_blank_rows(), the
        # master Onboarding Step it points at is itself blank/broken -
        # never show a genuinely empty cell for that, since it's
        # indistinguishable from a rendering bug and impossible to
        # report precisely. Falling back to the record's own name (e.g.
        # "ONB-00023") makes a broken row identifiable and fixable
        # instead of silently invisible.
        step_name = row.step_name or ("Unnamed step (" + (row.onboarding_step or row.name) + ")")
        stage = row.stage or "Unassigned"

        row_dict = {
            "name": row.name,
            "step_name": step_name,
            "owner_type": row.owner_type,
            "status": row.status,
            "expected_result": row.expected_result or "",
            "where_it_happens": row.where_it_happens or "",
            "link_url": row.link_url or "",
            "completed_on": row.completed_on,
            "notes": row.notes or "",
            "is_locked": _is_locked(row, done_step_names),
        }

        if stage not in stage_index:
            stage_index[stage] = len(stages)
            stages.append({"stage": stage, "steps": []})

        stages[stage_index[stage]]["steps"].append(row_dict)

    return stages


@frappe.whitelist()
def get_my_onboarding_steps(coach=None):
    coach_name = _resolve_target_coach(coach)

    rows = frappe.get_all(
        COACH_ONBOARDING_STEP_DOCTYPE,
        filters={"coach": coach_name},
        fields=COACH_STEP_FIELDS,
    )

    # A coach can end up with start_onboarding ticked but zero rows -
    # e.g. a cleanup patch removing a batch that was entirely created
    # from broken master data (as happened here), or any other future
    # reason rows might legitimately need clearing out. Rather than
    # leave that coach stranded until someone remembers to re-tick the
    # checkbox (which is a no-op if it's already ticked - provisioning
    # only fires on the tick actually changing), re-provision right
    # here so the page just works again on the next load.
    if not rows and frappe.db.get_value("Coach", coach_name, "start_onboarding"):
        _create_coach_onboarding_steps(coach_name)
        rows = frappe.get_all(
            COACH_ONBOARDING_STEP_DOCTYPE,
            filters={"coach": coach_name},
            fields=COACH_STEP_FIELDS,
        )

    _repair_blank_rows(rows)
    rows = sorted(rows, key=lambda row: (row.stage_sort_order or 0, row.sort_order or 0))

    total = len(rows)
    done = len([row for row in rows if row.status == "Done"])

    return {
        "coach": coach_name,
        "started": total > 0,
        "total_steps": total,
        "done_steps": done,
        "stages": _group_by_stage(rows),
    }


@frappe.whitelist()
def mark_step_done(step_name=None, coach=None):
    """
    A coach marks their own Coach-owned step done. HQ-owned steps are
    never completable from here - see mark_step_done_for_coach.
    """
    step_name = coalesce_str("step_name", step_name)
    coach_name = _resolve_target_coach(coach)

    row = frappe.get_doc(COACH_ONBOARDING_STEP_DOCTYPE, step_name)

    if row.coach != coach_name:
        frappe.throw(_("You do not have permission to update this step."), frappe.PermissionError)

    if row.owner_type != "Coach":
        frappe.throw(_("This step is owned by HQ - only HQ can mark it done."))

    if row.status == "Done":
        return {"ok": True, "status": row.status}

    row.status = "Done"
    row.save(ignore_permissions=True)
    frappe.db.commit()

    return {"ok": True, "status": row.status}


@frappe.whitelist()
def mark_step_done_for_coach(step_name=None, status=None):
    """
    HQ marking a step (their own, or a coach's) done or updating its
    status - e.g. moving something to "Waiting on HQ" or "Ready for You".
    """
    if not is_franchisor_user():
        frappe.throw(_("You do not have permission to do this."), frappe.PermissionError)

    step_name = coalesce_str("step_name", step_name)
    status = coalesce_str("status", status) or "Done"

    valid_statuses = {"Not Started", "In Progress", "Waiting on HQ", "Ready for You", "Done"}
    if status not in valid_statuses:
        frappe.throw(_("Invalid status."))

    row = frappe.get_doc(COACH_ONBOARDING_STEP_DOCTYPE, step_name)
    row.status = status
    row.save(ignore_permissions=True)
    frappe.db.commit()

    return {"ok": True, "status": row.status}


def _ensure_all_started_coaches_provisioned():
    """
    Same self-healing as get_my_onboarding_steps, but for every coach at
    once - the franchisor overview queries Coach Onboarding Step rows
    directly rather than going through that function, so a coach with
    start_onboarding ticked but no rows (e.g. a cleanup patch clearing
    out a batch made from broken master data) would otherwise just be
    silently missing from this list instead of showing up needing
    attention.
    """
    started_coaches = frappe.get_all("Coach", filters={"start_onboarding": 1}, pluck="name")
    if not started_coaches:
        return

    provisioned = set(frappe.get_all(
        COACH_ONBOARDING_STEP_DOCTYPE,
        filters={"coach": ["in", started_coaches]},
        pluck="coach",
    ))

    for coach_name in started_coaches:
        if coach_name not in provisioned:
            _create_coach_onboarding_steps(coach_name)


@frappe.whitelist()
def get_all_coaches_onboarding_progress():
    """
    Franchisor overview: every coach currently mid-onboarding (has at
    least one Coach Onboarding Step row), their current stage, and how
    many steps are sitting on HQ's side of the fence.
    """
    if not is_franchisor_user():
        frappe.throw(_("You do not have permission to view this."), frappe.PermissionError)

    _ensure_all_started_coaches_provisioned()

    rows = frappe.get_all(
        COACH_ONBOARDING_STEP_DOCTYPE,
        fields=["coach", "stage", "stage_sort_order", "owner_type", "status"],
        order_by="coach asc, stage_sort_order asc, sort_order asc",
    )

    if not rows:
        return []

    coach_names = list({row.coach for row in rows})
    coach_labels = {
        c.name: (c.coach_name or c.name)
        for c in frappe.get_all("Coach", filters={"name": ["in", coach_names]}, fields=["name", "coach_name"])
    } if frappe.get_meta("Coach").has_field("coach_name") else {name: name for name in coach_names}

    by_coach = {}
    for row in rows:
        entry = by_coach.setdefault(row.coach, {
            "coach": row.coach,
            "coach_label": coach_labels.get(row.coach, row.coach),
            "total_steps": 0,
            "done_steps": 0,
            "waiting_on_hq": 0,
            "current_stage": None,
        })
        entry["total_steps"] += 1
        if row.status == "Done":
            entry["done_steps"] += 1
        if row.status == "Waiting on HQ":
            entry["waiting_on_hq"] += 1
        if row.status != "Done" and entry["current_stage"] is None:
            entry["current_stage"] = row.stage

    results = list(by_coach.values())
    for entry in results:
        if entry["current_stage"] is None:
            entry["current_stage"] = "Complete"

    return results


@frappe.whitelist()
def get_onboarding_step_master_list():
    """
    Every active Onboarding Step, for HQ's "Manage Step List" screen -
    lets HQ add/edit a step's link_url straight from the dashboard
    instead of needing Desk access.
    """
    if not is_franchisor_user():
        frappe.throw(_("You do not have permission to view this."), frappe.PermissionError)

    return frappe.get_all(
        ONBOARDING_STEP_DOCTYPE,
        filters=[["is_active", "=", 1], ["stage", "is", "set"]],
        fields=["name", "step_name", "stage", "stage_sort_order", "sort_order", "owner_type", "expected_result", "link_url"],
        order_by="stage_sort_order asc, sort_order asc",
    )


@frappe.whitelist()
def update_onboarding_step_master(step_name=None, link_url=None):
    """
    Saves a step's Go link from the dashboard's step manager. Unlike
    the other fields copied onto Coach Onboarding Step at creation time
    (deliberately a snapshot, so a later wording edit doesn't rewrite a
    coach's history), the link is treated as always-current - it's a
    "where do I go" pointer, not a record of what a coach was told, so
    an HQ correction or addition here is pushed onto every coach's
    existing row for this step too, not just coaches who start from now
    on.
    """
    if not is_franchisor_user():
        frappe.throw(_("You do not have permission to do this."), frappe.PermissionError)

    step_name = coalesce_str("step_name", step_name)
    link_url = coalesce_str("link_url", link_url)

    if not step_name or not frappe.db.exists(ONBOARDING_STEP_DOCTYPE, step_name):
        frappe.throw(_("Onboarding step not found."))

    frappe.db.set_value(ONBOARDING_STEP_DOCTYPE, step_name, "link_url", link_url, update_modified=False)

    if frappe.db.exists("DocType", COACH_ONBOARDING_STEP_DOCTYPE):
        frappe.db.set_value(
            COACH_ONBOARDING_STEP_DOCTYPE,
            {"onboarding_step": step_name},
            "link_url",
            link_url,
            update_modified=False,
        )

    frappe.db.commit()

    return {"ok": True, "link_url": link_url}
