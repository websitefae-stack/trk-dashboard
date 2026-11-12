"""
Franchisor-facing LMS admin tools that aren't tied to onboarding -
originally built (and still used) for sharing an onboarding step's
lesson across two courses, but the underlying operation is just plain
LMS Course/Chapter management, nothing onboarding-specific about it.
Split out from onboarding.py into its own module, and the "Share an
Existing Module With Another Course" tool itself moved onto its own
franchisor_db/lms_tools page, so Ashley can reuse a module/chapter
across any two courses whenever she sets up a new one - not only when
it happens to also be an onboarding step's Go link.

get_lms_chapters() itself stays in onboarding.py - it's also used
there for the Manage Step List's own per-step "which chapter does this
step link to" picker, not just this module's own share tool.
"""

import frappe
from frappe import _

from dashboard.api.shared.permissions import is_franchisor_user
from dashboard.api.shared.utils import coalesce_str
from dashboard.api.shared.onboarding import (
    LMS_COURSE_CHAPTER_DOCTYPE,
    LMS_CHAPTER_REFERENCE_DOCTYPE,
)


@frappe.whitelist()
def get_lms_courses():
    """
    Every LMS Course, for the "Add it to this course" side of the Share
    an Existing Module tool - deliberately NOT derived from
    onboarding.get_lms_chapters()'s own chapter list, which only ever
    lists courses that already have at least one chapter in them. A
    brand new course (e.g. a just-created Session Worker-only course,
    empty until its first chapter is shared into it) would never appear
    as a share target otherwise - exactly the "still not able to link
    lessons to a second course" symptom Ashley hit, since there was
    nothing wrong with link_existing_chapter_to_course itself, the new
    course just never showed up to pick in the first place.
    """
    if not is_franchisor_user():
        frappe.throw(_("You do not have permission to view this."), frappe.PermissionError)

    if not frappe.db.exists("DocType", "LMS Course"):
        return []

    return frappe.get_all(
        "LMS Course",
        fields=["name", "title"],
        order_by="title asc",
    )


def _chapter_reference_parentfield():
    """
    The fieldname on LMS Course holding its Chapter Reference child table
    - found from the doctype's own metadata (a Table field whose options
    is "Chapter Reference") rather than guessed, since this app doesn't
    own Frappe LMS's schema and the exact fieldname was never confirmed
    against its source.
    """
    for field in frappe.get_meta("LMS Course").fields:
        if field.fieldtype == "Table" and field.options == LMS_CHAPTER_REFERENCE_DOCTYPE:
            return field.fieldname
    return None


@frappe.whitelist()
def link_existing_chapter_to_course(course=None, chapter_name=None):
    """
    Shares an existing LMS chapter (and every lesson already in it) with
    a second course, without duplicating either - originally built for
    "link a module and its lessons to 2 courses" (an onboarding step's
    lesson shared between the Coach course and a Session Worker-only
    one), but a plain LMS operation with no onboarding dependency - this
    now backs the general-purpose franchisor_db/lms_tools page too, for
    reusing a module across any two courses, onboarding or not.

    Adds one new Chapter Reference row under the target course, pointing
    at the chapter that already exists under its original course -
    nothing about the chapter or its lessons is copied or re-created.
    Course Chapter's own "course" field still names only its original
    course (Frappe LMS's own schema - a chapter belongs to exactly one
    "home" course there), but this app's own onboarding Go-link/
    completion logic (onboarding._resolve_lms_chapter) is built to trust
    whichever course a step's own master record says to use, not that
    field, so an onboarding step configured against this second course
    still resolves correctly - see its own docstring. The one thing
    this doesn't fix is cosmetic: if Frappe LMS's own front-end shows
    "which course this chapter belongs to" anywhere in its breadcrumbs/
    navigation, that will still say the original course, not this new
    one.

    Safe to call again for the same pair - a chapter already referenced
    under a course is left alone, not duplicated.
    """
    if not is_franchisor_user():
        frappe.throw(_("You do not have permission to do this."), frappe.PermissionError)

    course = coalesce_str("course", course)
    chapter_name = coalesce_str("chapter_name", chapter_name)

    if not frappe.db.exists("DocType", LMS_COURSE_CHAPTER_DOCTYPE):
        frappe.throw(_("Frappe LMS doesn't appear to be installed on this site."))

    if not course or not frappe.db.exists("LMS Course", course):
        frappe.throw(_("Course not found."))

    if not chapter_name or not frappe.db.exists(LMS_COURSE_CHAPTER_DOCTYPE, chapter_name):
        frappe.throw(_("Chapter not found."))

    if frappe.db.exists(LMS_CHAPTER_REFERENCE_DOCTYPE, {"parent": course, "chapter": chapter_name}):
        return {"ok": True, "already_linked": True}

    parentfield = _chapter_reference_parentfield()
    if not parentfield:
        frappe.throw(_("Could not find LMS Course's chapters field - check Frappe LMS is installed and up to date."))

    existing_idx = frappe.db.get_all(
        LMS_CHAPTER_REFERENCE_DOCTYPE, filters={"parent": course}, fields=["idx"], order_by="idx desc", limit_page_length=1,
    )
    next_idx = (existing_idx[0].idx + 1) if existing_idx else 1

    frappe.get_doc({
        "doctype": LMS_CHAPTER_REFERENCE_DOCTYPE,
        "parent": course,
        "parenttype": "LMS Course",
        "parentfield": parentfield,
        "chapter": chapter_name,
        "idx": next_idx,
    }).insert(ignore_permissions=True)
    frappe.db.commit()

    return {"ok": True, "already_linked": False}
