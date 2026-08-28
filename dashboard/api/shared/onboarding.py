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
    "expected_result", "where_it_happens", "link_url",
    "lms_course", "lms_chapter", "lms_lesson_number", "hidden_from_coach",
    "depends_on_step", "stage_sort_order", "sort_order", "completed_on", "completed_by", "notes",
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


MASTER_STEP_LIVE_FIELDS = ["link_url", "lms_course", "lms_chapter", "lms_lesson_number", "hidden_from_coach"]


def sync_master_step_link_fields(doc, method=None):
    """
    Coach Onboarding Master Step.on_update hook. link_url/lms_course/
    lms_chapter/lms_lesson_number are "where do I go / how do I know
    it's done" pointers, treated as always-current rather than a
    point-in-time snapshot (unlike step_name/expected_result/etc, which
    stay whatever a coach was actually told at the time) - so a change
    here needs to reach every Coach Onboarding Step row already created
    from this master step, not just coaches who start from now on.

    This runs on every save regardless of how it happened (a direct Desk
    edit, the franchisor Manage Step List screen, Data Import...) - it
    used to only happen via update_onboarding_step_master's own explicit
    push, which meant a plain Desk edit silently never reached any
    coach's already-existing row.
    """
    if not frappe.db.exists("DocType", COACH_ONBOARDING_STEP_DOCTYPE):
        return

    try:
        updates = {field: doc.get(field) for field in MASTER_STEP_LIVE_FIELDS}
        frappe.db.set_value(
            COACH_ONBOARDING_STEP_DOCTYPE, {"onboarding_step": doc.name}, updates, update_modified=False,
        )
        frappe.db.commit()
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Master Step Link Field Sync Failed - {doc.name}")


def sync_master_step_active_state(doc, method=None):
    """
    Coach Onboarding Master Step.on_update hook. Unticking Active used to
    only stop this step being provisioned to a coach newly starting
    onboarding (see the is_active filter in _create_coach_onboarding_steps)
    - a coach who already had the step kept it forever, "retired" or not.
    Unticking now removes it from every coach's checklist outright,
    regardless of its status there - "we no longer need this step" means
    gone, not lingering as a stale row. Re-ticking adds it back onto
    every coach already mid-onboarding who doesn't already have it, the
    same backfill a one-off patch like add_print_materials_onboarding_step
    would otherwise be needed for.
    """
    if not frappe.db.exists("DocType", COACH_ONBOARDING_STEP_DOCTYPE):
        return

    try:
        if doc.is_active:
            _add_master_step_to_existing_coaches(doc)
        else:
            frappe.db.delete(COACH_ONBOARDING_STEP_DOCTYPE, {"onboarding_step": doc.name})
            frappe.db.commit()
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Master Step Active State Sync Failed - {doc.name}")


def remove_coach_steps_on_master_step_delete(doc, method=None):
    """
    Coach Onboarding Master Step.on_trash hook - deleting the master step
    outright (rather than unticking Active first) used to leave every
    coach's own Coach Onboarding Step row for it stranded, pointing at a
    master step that no longer exists. Those orphaned rows still counted
    towards total_steps in get_my_onboarding_steps, which is why "how
    many steps are there" could silently drift from the real current
    list after a Desk cleanup. Same treatment as unticking Active.
    """
    if not frappe.db.exists("DocType", COACH_ONBOARDING_STEP_DOCTYPE):
        return

    try:
        frappe.db.delete(COACH_ONBOARDING_STEP_DOCTYPE, {"onboarding_step": doc.name})
        frappe.db.commit()
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Master Step Delete Cleanup Failed - {doc.name}")


def _add_master_step_to_existing_coaches(doc):
    if not doc.stage:
        return

    onboarding_coaches = set(frappe.get_all(COACH_ONBOARDING_STEP_DOCTYPE, pluck="coach"))
    already_have_it = set(frappe.get_all(
        COACH_ONBOARDING_STEP_DOCTYPE, filters={"onboarding_step": doc.name}, pluck="coach",
    ))

    for coach_name in onboarding_coaches - already_have_it:
        try:
            frappe.get_doc({
                "doctype": COACH_ONBOARDING_STEP_DOCTYPE,
                "coach": coach_name,
                "onboarding_step": doc.name,
                "status": "Not Started",
                "step_name": doc.step_name,
                "stage": doc.stage,
                "owner_type": doc.owner_type,
                "stage_sort_order": doc.stage_sort_order,
                "sort_order": doc.sort_order,
                "expected_result": doc.expected_result,
                "where_it_happens": doc.where_it_happens,
                "link_url": doc.link_url,
                "lms_course": doc.lms_course,
                "lms_chapter": doc.lms_chapter,
                "lms_lesson_number": doc.lms_lesson_number,
                "hidden_from_coach": doc.hidden_from_coach,
                "depends_on_step": doc.depends_on,
            }).insert(ignore_permissions=True)
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Master Step Reactivation Backfill Failed - {coach_name}")

    frappe.db.commit()


def _create_coach_onboarding_steps(coach_name):
    # Locks the Coach row for the rest of this function, so two nearly-
    # simultaneous requests for the same coach (e.g. two staff members
    # both opening this coach's onboarding at once) can't both pass the
    # "does this coach already have steps" check before either has
    # actually created any - a real race that happened in production,
    # duplicating a coach's entire step list every time it occurred.
    # The second caller blocks here until the first one's transaction
    # commits, then sees the steps the first one just created and exits
    # via the check below instead of creating a second full batch.
    frappe.db.sql("SELECT name FROM `tabCoach` WHERE name=%s FOR UPDATE", coach_name)

    if frappe.db.exists(COACH_ONBOARDING_STEP_DOCTYPE, {"coach": coach_name}):
        return

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
            "sort_order", "expected_result", "where_it_happens", "link_url",
            "lms_course", "lms_chapter", "lms_lesson_number", "hidden_from_coach", "depends_on",
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
            "lms_course": step.lms_course,
            "lms_chapter": step.lms_chapter,
            "lms_lesson_number": step.lms_lesson_number,
            "hidden_from_coach": step.hidden_from_coach,
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
    ("lms_course", "lms_course"),
    ("lms_chapter", "lms_chapter"),
    ("lms_lesson_number", "lms_lesson_number"),
    ("hidden_from_coach", "hidden_from_coach"),
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


# Frappe LMS (frappe/lms) is a separate app, not one of the repos this
# app is built alongside, so its schema is probed rather than assumed -
# every lookup below returns None/skips quietly if LMS isn't installed,
# same defensive style as client_portal's own LMS integration
# (_get_course_enrollments there). Doctype names and the URL shape below
# were confirmed against the actual frappe/lms source (course.chapters is
# a Chapter Reference table, chapter.lessons is a Lesson Reference table,
# and the frontend route is /lms/courses/<course>/learn/<chapter
# idx>-<lesson idx>, both idx values being each row's 1-based position in
# its parent table - not the chapter/lesson's own document name).
LMS_COURSE_CHAPTER_DOCTYPE = "Course Chapter"
LMS_CHAPTER_REFERENCE_DOCTYPE = "Chapter Reference"
LMS_LESSON_REFERENCE_DOCTYPE = "Lesson Reference"
LMS_COURSE_PROGRESS_DOCTYPE = "LMS Course Progress"


def _resolve_lms_chapter(chapter_name):
    """
    chapter_name is the actual Course Chapter document name (e.g. "0001
    Access your emails with Chantelle Venter") - LMS Chapter is a real
    Link field on the master step now, picked directly in the Desk (or
    via the Manage Step List picker), not a free-text title to match
    against. Returns everything needed to build a working link and check
    completion, or None if LMS isn't installed, the chapter no longer
    exists, or it has no lessons.
    """
    if not chapter_name or not frappe.db.exists("DocType", LMS_COURSE_CHAPTER_DOCTYPE):
        return None

    course = frappe.db.get_value(LMS_COURSE_CHAPTER_DOCTYPE, chapter_name, "course")
    if not course:
        return None

    chapter_idx = frappe.db.get_value(
        LMS_CHAPTER_REFERENCE_DOCTYPE, {"parent": course, "chapter": chapter_name}, "idx",
    )
    if not chapter_idx:
        return None

    lesson_count = frappe.db.count(LMS_LESSON_REFERENCE_DOCTYPE, {"parent": chapter_name})
    if not lesson_count:
        return None

    return {
        "course": course,
        "chapter_name": chapter_name,
        "chapter_idx": chapter_idx,
        "lesson_count": lesson_count,
    }


def _lms_chapter_is_complete(user, chapter_info):
    completed = frappe.db.count(
        LMS_COURSE_PROGRESS_DOCTYPE,
        {"member": user, "chapter": chapter_info["chapter_name"], "status": "Complete"},
    )
    return completed >= chapter_info["lesson_count"]


def _apply_lms_progress_overrides(rows, user):
    """
    A step with LMS Chapter set gets its Go link and Done status worked
    out live from the coach's actual progress through that chapter, the
    same "derived from the real system of record, not self-reported"
    treatment Stage 5 Policies and Operations Manual already get from
    Coach Document Requirement. Mutates rows in place (frappe._dict from
    frappe.get_all supports arbitrary keys) so the existing total/done
    counting and _group_by_stage in get_my_onboarding_steps pick this up
    automatically. Newly-detected completion is persisted (not just
    returned) so completed_on is a real historical date, not "now" on
    every page load.
    """
    if not user:
        return

    for row in rows:
        if row.where_it_happens != "LMS" or not row.get("lms_chapter"):
            continue

        try:
            chapter_info = _resolve_lms_chapter(row.lms_chapter)
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"LMS Chapter Resolve Failed - {row.name}")
            continue

        if not chapter_info:
            # Configured but not resolving - genuinely worth knowing about
            # (the chapter got renamed/deleted in the LMS since it was
            # picked, etc.), not just silently left showing "Complete the
            # course" with no Go link.
            frappe.log_error(
                f"Step: {row.name}\nChapter: {row.lms_chapter}",
                "LMS Chapter Not Found",
            )
            continue

        lesson_number = row.get("lms_lesson_number") or 1
        row["link_url"] = "/lms/courses/{0}/learn/{1}-{2}".format(
            chapter_info["course"], chapter_info["chapter_idx"], lesson_number,
        )

        if row.status != "Done":
            try:
                if _lms_chapter_is_complete(user, chapter_info):
                    completed_on = now_datetime()
                    frappe.db.set_value(
                        COACH_ONBOARDING_STEP_DOCTYPE,
                        row.name,
                        {"status": "Done", "completed_on": completed_on, "completed_by": user},
                        update_modified=False,
                    )
                    row["status"] = "Done"
                    row["completed_on"] = completed_on
                    frappe.db.commit()
            except Exception:
                frappe.log_error(frappe.get_traceback(), f"LMS Chapter Completion Check Failed - {row.name}")


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
            "hidden_from_coach": bool(row.hidden_from_coach),
            # Carried through so _append_step_to_stage can slot a dynamic
            # step (e.g. Operations Manual) in among these by position
            # rather than always at the very end of the stage.
            "sort_order": row.sort_order or 0,
        }

        if stage not in stage_index:
            stage_index[stage] = len(stages)
            stages.append({"stage": stage, "steps": []})

        stages[stage_index[stage]]["steps"].append(row_dict)

    return stages


@frappe.whitelist()
def coach_has_onboarding_steps():
    """
    Sidebar check - a coach who was never opted into the onboarding
    journey (most existing coaches) shouldn't see the Onboarding link at
    all, and one who's fully finished it shouldn't either (all_done) -
    the link disappearing is itself the "you're done" signal, nothing
    left to keep checking back on. The franchisor's own overview/drill-
    down keeps showing a completed coach regardless - this only ever
    hides the coach's own sidebar link.
    """
    coach_name = get_current_coach_name(optional=True)
    if not coach_name:
        return {"has_steps": False, "all_done": False}

    if not frappe.db.exists(COACH_ONBOARDING_STEP_DOCTYPE, {"coach": coach_name}):
        return {"has_steps": False, "all_done": False}

    progress = get_my_onboarding_steps()
    all_done = bool(progress["total_steps"]) and progress["done_steps"] >= progress["total_steps"]

    return {"has_steps": True, "all_done": all_done}


@frappe.whitelist()
def get_my_onboarding_steps(coach=None):
    coach_name = _resolve_target_coach(coach)

    # A franchisor drilled into someone else's checklist needs view_as/
    # viewer on the document link too, or document_view has no way to
    # know she's allowed to be looking at a coach she isn't - it just
    # redirects her out. coalesce_str("coach", coach) here mirrors
    # _resolve_target_coach()'s own check for "was an explicit coach
    # actually asked for", not just "who ended up being resolved". Also
    # what gates whether a Hidden From Coach step (an HQ-only task the
    # coach never sees at all, not even locked/greyed-out - see
    # sync_master_step_active_state's sibling hidden_from_coach field)
    # is filtered out below or left in for HQ's own view of it.
    is_drill_down = bool(coalesce_str("coach", coach)) and is_franchisor_user()
    view_as_coach = coach_name if is_drill_down else None

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
        frappe.db.commit()
        rows = frappe.get_all(
            COACH_ONBOARDING_STEP_DOCTYPE,
            filters={"coach": coach_name},
            fields=COACH_STEP_FIELDS,
        )

    _repair_blank_rows(rows)
    _apply_lms_progress_overrides(rows, frappe.db.get_value("Coach", coach_name, "user"))

    # Hidden From Coach steps are an HQ-only task the coach never sees at
    # all - not filtered from the counts either, since a coach's own
    # progress percentage shouldn't be dragged down by something they
    # can't even see or act on. HQ's own drill-down view keeps them.
    if not is_drill_down:
        rows = [row for row in rows if not row.hidden_from_coach]

    rows = sorted(rows, key=lambda row: (row.stage_sort_order or 0, row.sort_order or 0))

    stages = _group_by_stage(rows)
    policy_stage = _dynamic_policies_stage(coach_name, view_as_coach=view_as_coach)
    _insert_dynamic_stage(stages, policy_stage, after_stage_number=4)

    operations_manual_step = _dynamic_operations_manual_step(coach_name, view_as_coach=view_as_coach)
    if operations_manual_step:
        _append_step_to_stage(stages, stage_number=3, step=operations_manual_step)

    total = len(rows) + len(policy_stage["steps"]) + (1 if operations_manual_step else 0)
    done = len([row for row in rows if row.status == "Done"])
    done += len([step for step in policy_stage["steps"] if step["status"] == "Completed"])
    if operations_manual_step and operations_manual_step["status"] == "Completed":
        done += 1

    return {
        "coach": coach_name,
        "started": total > 0,
        "total_steps": total,
        "done_steps": done,
        "stages": stages,
    }


POLICY_DOCUMENT_TYPES = ["Policy", "Procedure"]


def _dynamic_policies_stage(coach_name, view_as_coach=None):
    """
    Stage 5 (Policies) has no static Coach Onboarding Step rows behind it
    - it's built live from Coach Document Requirement instead, so it
    always reflects whatever Policy/Procedure documents currently exist
    (add a new one in the Desk and it just shows up here, no onboarding
    step needs creating for it). A step here is automatically "Done" the
    moment the coach actually acknowledges that document on the
    Documents page - there's nothing to keep in sync, since it's the
    same underlying record being read, not a copy of it. Never locked -
    the whole point is these are readable before Training Day, not
    gated behind it like everything else from here on.

    view_as_coach is set only when a franchisor is looking at someone
    else's checklist (see get_my_onboarding_steps) - document_view needs
    view_as/viewer on the URL in that case, or it has no way to know
    she's allowed to be looking at a coach she isn't, and redirects her
    out entirely.
    """
    user = frappe.db.get_value("Coach", coach_name, "user")
    if not user:
        return {"stage": "Stage 5 - Policies", "steps": []}

    rows = frappe.get_all(
        "Coach Document Requirement",
        filters={"user": user, "document_type": ["in", POLICY_DOCUMENT_TYPES]},
        fields=["name", "document_title", "document_type", "status", "completed_on"],
        order_by="document_type asc, document_title asc",
    )

    if view_as_coach:
        extra_params = "&view_as=" + frappe.utils.quote(view_as_coach) + "&viewer=franchisor"
    else:
        extra_params = "&back_to=" + frappe.utils.quote("/coach_db/onboarding")

    steps = []
    for row in rows:
        label = row.document_title or row.name
        if row.document_type == "Procedure":
            label += " (Procedure)"

        steps.append({
            "name": row.name,
            "step_name": label,
            "owner_type": "Coach",
            "status": row.status,
            "expected_result": "",
            "where_it_happens": "Frappe - Documents",
            # Straight to this specific document (document_view reads
            # ?name=<requirement>), not the general list - the whole
            # point of the Go link is landing exactly where the coach
            # needs to act, not one extra click away from it.
            "link_url": "/coach_db/document_view?name=" + row.name + extra_params,
            "completed_on": row.completed_on,
            "notes": "",
            "is_locked": False,
            "read_only": True,
        })

    return {"stage": "Stage 5 - Policies", "steps": steps}


# This is deliberately the one specific Practice Document ID, not a
# document_type filter (e.g. "Practice Manual") - Ashley was explicit that
# this is only for the Operations Manual itself, not every document of
# that type, so a future second "Practice Manual" document must never be
# swept in here by accident. Update this if the Operations Manual's
# Practice Document is ever recreated under a different ID.
OPERATIONS_MANUAL_PRACTICE_DOCUMENT = "9006"

# Operations Manual has no real Coach Onboarding Master Step row of its
# own (it's built live from a Coach Document Requirement - see
# _dynamic_operations_manual_step), so it has no natural "Sort Order
# Within Stage" to compare against. Pinning it to this fixed, deliberately
# high value lets any real Stage 3 step be placed after it just by giving
# that step a Sort Order Within Stage higher than this - without needing
# a real stage restructure. Real Stage 3 steps should stay well below
# this (existing ones already are); anything wanting to land after
# Operations Manual should use a value above it, e.g. 1001, 1002.
OPERATIONS_MANUAL_SORT_ORDER = 1000


def _dynamic_operations_manual_step(coach_name, view_as_coach=None):
    """
    Same mechanism as _dynamic_policies_stage, but for a single named
    document (the Operations Manual) rather than a whole document_type -
    it used to be a static "complete this in the LMS" step, now it's
    pulled live from the coach's own Coach Document Requirement for that
    one Practice Document, so it's automatically "Done" the moment the
    coach acknowledges it on the Documents page. Returns None if this
    coach has no requirement for it yet (e.g. brand access hasn't synced
    one in), in which case the step is simply omitted rather than shown
    broken.
    """
    user = frappe.db.get_value("Coach", coach_name, "user")
    if not user:
        return None

    row = frappe.db.get_value(
        "Coach Document Requirement",
        {"user": user, "practice_document": OPERATIONS_MANUAL_PRACTICE_DOCUMENT},
        ["name", "document_title", "status", "completed_on"],
        as_dict=True,
    )
    if not row:
        return None

    if view_as_coach:
        extra_params = "&view_as=" + frappe.utils.quote(view_as_coach) + "&viewer=franchisor"
    else:
        extra_params = "&back_to=" + frappe.utils.quote("/coach_db/onboarding")

    return {
        "name": row.name,
        "step_name": row.document_title or "Operations Manual",
        "owner_type": "Coach",
        "status": row.status,
        "expected_result": "",
        "where_it_happens": "Frappe - Documents",
        "link_url": "/coach_db/document_view?name=" + row.name + extra_params,
        "completed_on": row.completed_on,
        "notes": "",
        "is_locked": False,
        "read_only": True,
        "sort_order": OPERATIONS_MANUAL_SORT_ORDER,
    }


def _append_step_to_stage(stages, stage_number, step):
    for stage in stages:
        try:
            number = int((stage["stage"] or "").split(" ")[1])
        except (IndexError, ValueError):
            continue
        if number == stage_number:
            # Inserted by sort_order rather than blindly appended last -
            # a real step in this stage with a higher Sort Order Within
            # Stage than this dynamic step's own (see e.g.
            # OPERATIONS_MANUAL_SORT_ORDER) lands after it, not before.
            step_sort_order = step.get("sort_order", 0) or 0
            insert_at = len(stage["steps"])
            for index, existing in enumerate(stage["steps"]):
                if (existing.get("sort_order", 0) or 0) > step_sort_order:
                    insert_at = index
                    break
            stage["steps"].insert(insert_at, step)
            return


def _insert_dynamic_stage(stages, dynamic_stage, after_stage_number):
    def stage_number(label):
        try:
            return int((label or "").split(" ")[1])
        except (IndexError, ValueError):
            return 0

    insert_at = len(stages)
    for index, stage in enumerate(stages):
        if stage_number(stage["stage"]) > after_stage_number:
            insert_at = index
            break

    stages.insert(insert_at, dynamic_stage)


@frappe.whitelist()
def mark_step_done(step_name=None, coach=None):
    """
    A coach marks their own Coach-owned step done. HQ-owned steps are
    never completable from here - see mark_step_done_for_coach.
    """
    step_name = coalesce_str("step_name", step_name)
    coach_name = _resolve_target_coach(coach)

    # Coach Onboarding Step's own DocType permissions only grant
    # System Manager - a coach never has that role, so without this,
    # loading their own step here throws a permission error before
    # this function's own authorization logic (the coach/owner_type
    # checks below) ever gets a chance to run. save(ignore_permissions)
    # alone doesn't cover it - loading the document is a separate step.
    frappe.flags.ignore_permissions = True

    row = frappe.get_doc(COACH_ONBOARDING_STEP_DOCTYPE, step_name)

    if row.coach != coach_name:
        frappe.throw(_("You do not have permission to update this step."), frappe.PermissionError)

    if row.owner_type != "Coach":
        frappe.throw(_("This step is owned by HQ - only HQ can mark it done."))

    # An LMS-based step is completed by actually finishing the course,
    # not by self-reporting it here - a misclick on this button is
    # exactly what previously marked a step Done with no course
    # completion behind it. The dashboard already hides the Mark Done
    # button for these (see isLmsStep in onboarding.js), this is the
    # same rule enforced server-side so it can't be bypassed by calling
    # this endpoint directly.
    if row.where_it_happens == "LMS":
        frappe.throw(_("This step is completed in the course itself, not marked done here."))

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

    # See the matching comment in mark_step_done() - loading the
    # document is a separate step from saving it, and
    # save(ignore_permissions) alone doesn't cover a read-permission
    # failure on the load itself.
    frappe.flags.ignore_permissions = True

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
            frappe.db.commit()


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
            "waiting_on_hq": 0,
            "current_stage": None,
        })
        if row.status == "Waiting on HQ":
            entry["waiting_on_hq"] += 1
        if row.status != "Done" and entry["current_stage"] is None:
            entry["current_stage"] = row.stage

    results = []
    for coach_name, entry in by_coach.items():
        # total_steps/done_steps deliberately come from
        # get_my_onboarding_steps() - the exact same function that
        # coach's own onboarding page (and HQ's own drill-down into it)
        # uses - rather than a second, simpler count of raw Coach
        # Onboarding Step rows. That raw count leaves out the dynamic
        # Policies stage and Operations Manual step (neither has a
        # static row behind it - see _dynamic_policies_stage/
        # _dynamic_operations_manual_step), which is why this overview
        # used to show a smaller total than the coach's own page.
        progress = get_my_onboarding_steps(coach=coach_name)
        entry["total_steps"] = progress["total_steps"]
        entry["done_steps"] = progress["done_steps"]
        if entry["current_stage"] is None:
            entry["current_stage"] = "Complete"
        results.append(entry)

    return results


@frappe.whitelist()
def get_onboarding_step_master_list():
    """
    Every active Onboarding Step, for HQ's "Manage Step List" screen -
    lets HQ add/edit a step's link_url (or, for an LMS step, its LMS
    Chapter Title - see _apply_lms_progress_overrides) straight from the
    dashboard instead of needing Desk access.
    """
    if not is_franchisor_user():
        frappe.throw(_("You do not have permission to view this."), frappe.PermissionError)

    return frappe.get_all(
        ONBOARDING_STEP_DOCTYPE,
        filters=[["is_active", "=", 1], ["stage", "is", "set"]],
        fields=[
            "name", "step_name", "stage", "stage_sort_order", "sort_order", "owner_type",
            "expected_result", "where_it_happens", "link_url",
            "lms_course", "lms_chapter", "lms_lesson_number",
        ],
        order_by="stage_sort_order asc, sort_order asc",
    )


@frappe.whitelist()
def get_lms_chapters():
    """
    Every chapter across every Frappe LMS course, each with its own
    lessons in order, in the same order HQ sees them in the LMS course
    editor sidebar (Chapter Reference.idx / Lesson Reference.idx), for the
    Manage Step List chapter+lesson picker - selecting from this stores
    the chapter's real document name (chapter_name), the same value LMS
    Chapter holds directly in the Desk now, not a title to match against.

    Wrapped in try/except (unlike the read-only helpers in
    _apply_lms_progress_overrides, which are only ever called for a step
    already configured to use LMS tracking) because this is the very
    first place a schema mismatch with what's actually installed would
    show up - logged rather than left as an unexplained empty dropdown.
    """
    if not is_franchisor_user():
        frappe.throw(_("You do not have permission to view this."), frappe.PermissionError)

    if not frappe.db.exists("DocType", LMS_COURSE_CHAPTER_DOCTYPE):
        return []

    try:
        course_titles = {
            course.name: course.title
            for course in frappe.get_all("LMS Course", fields=["name", "title"])
        }
        chapter_titles = {
            chapter.name: chapter.title
            for chapter in frappe.get_all(LMS_COURSE_CHAPTER_DOCTYPE, fields=["name", "title"])
        }
        lesson_titles = {
            lesson.name: lesson.title
            for lesson in frappe.get_all("Course Lesson", fields=["name", "title"])
        }

        lessons_by_chapter = {}
        for lesson_ref in frappe.get_all(
            LMS_LESSON_REFERENCE_DOCTYPE, fields=["parent", "idx", "lesson"], order_by="parent asc, idx asc",
        ):
            if lesson_ref.lesson not in lesson_titles:
                continue
            lessons_by_chapter.setdefault(lesson_ref.parent, []).append({
                "idx": lesson_ref.idx,
                "title": lesson_titles[lesson_ref.lesson],
            })

        references = frappe.get_all(
            LMS_CHAPTER_REFERENCE_DOCTYPE,
            fields=["parent", "chapter"],
            order_by="parent asc, idx asc",
        )

        return [
            {
                "course": reference.parent,
                "course_title": course_titles.get(reference.parent, reference.parent),
                "chapter_name": reference.chapter,
                "chapter_title": chapter_titles[reference.chapter],
                "lessons": lessons_by_chapter.get(reference.chapter, []),
            }
            for reference in references
            if reference.chapter in chapter_titles
        ]
    except Exception:
        frappe.log_error(frappe.get_traceback(), "get_lms_chapters failed")
        return []


@frappe.whitelist()
def update_onboarding_step_master(
    step_name=None, link_url=None, lms_course=None, lms_chapter=None, lms_lesson_number=None,
):
    """
    Saves a step's Go link (or LMS Course/Chapter/Lesson, picked from the
    get_lms_chapters dropdowns) from the dashboard's step manager. Unlike
    the other fields copied onto Coach Onboarding Step at creation time
    (deliberately a snapshot, so a later wording edit doesn't rewrite a
    coach's history), all of these are treated as always-current - they're
    "where do I go / how do I know it's done" pointers, not a record of
    what a coach was told, so an HQ correction or addition here is pushed
    onto every coach's existing row for this step too, not just coaches
    who start from now on.

    lms_chapter takes priority for the Go link once set - see
    _apply_lms_progress_overrides - so link_url is still saved here for
    when it's unset (or for a non-LMS step), but won't visibly do
    anything for a step that already has an LMS Chapter.
    """
    if not is_franchisor_user():
        frappe.throw(_("You do not have permission to do this."), frappe.PermissionError)

    step_name = coalesce_str("step_name", step_name)
    link_url = coalesce_str("link_url", link_url)
    lms_course = coalesce_str("lms_course", lms_course)
    lms_chapter = coalesce_str("lms_chapter", lms_chapter)
    lms_lesson_number = coalesce_str("lms_lesson_number", lms_lesson_number)

    if not step_name or not frappe.db.exists(ONBOARDING_STEP_DOCTYPE, step_name):
        frappe.throw(_("Onboarding step not found."))

    try:
        lms_lesson_number = int(lms_lesson_number) if lms_lesson_number else 1
    except ValueError:
        lms_lesson_number = 1

    updates = {
        "link_url": link_url,
        "lms_course": lms_course,
        "lms_chapter": lms_chapter,
        "lms_lesson_number": lms_lesson_number,
    }
    frappe.db.set_value(ONBOARDING_STEP_DOCTYPE, step_name, updates, update_modified=False)

    # Pushes these same values onto every coach already on this step -
    # see sync_master_step_link_fields (Coach Onboarding Master Step's
    # on_update hook). Called directly rather than via doc.save() here,
    # since frappe.db.set_value above (a fast targeted update, not a full
    # document save) doesn't fire doc_events on its own.
    sync_master_step_link_fields(frappe.get_doc(ONBOARDING_STEP_DOCTYPE, step_name))
    frappe.db.commit()

    return {
        "ok": True,
        "link_url": link_url,
        "lms_course": lms_course,
        "lms_chapter": lms_chapter,
        "lms_lesson_number": lms_lesson_number,
    }
