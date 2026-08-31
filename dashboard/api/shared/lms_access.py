"""
Locks a Frappe LMS course down to "enrolled/staff only" without touching
the course's own Published checkbox - Ashley found the hard way that
unpublishing a course blocks it for EVERYONE, including people already
enrolled in it (lms.lms.utils.get_course_details only checks membership
when the course is unpublished; when published it skips that check
entirely for everyone). So this uses its own field instead, and applies
the exact same "enrolled, instructor/moderator, or nothing" gate LMS
itself already uses for Course Lesson (see course_lesson.py's own
has_permission/get_permission_query_conditions in the Learning app - this
mirrors that pattern for LMS Course, which has neither natively) plus two
LMS-owned whitelisted functions that read the course directly rather than
through Frappe's permission-checked query layer.

What's covered:
- LMS Course's own has_permission/get_permission_query_conditions (this
  file, registered in hooks.py) - blocks a direct document read, and
  hides a restricted course from every course-listing query that goes
  through frappe.get_all/get_list without ignore_permissions (the public
  browse page, the featured/popular home-page widgets).
- get_course_details (lms.lms.utils) - the course "landing page" data
  fetch, called with frappe.db.get_value directly rather than through
  the permission-checked query layer, so it needs its own override (see
  hooks.py's override_whitelisted_methods) to apply the same gate.
- get_course_outline (lms.lms.utils) - the chapter/lesson title list
  that powers the sidebar, same reasoning, same override treatment.

What's NOT touched, deliberately: actual lesson body content already has
its own real access control in the Learning app itself (Course Lesson's
has_permission/get_permission_query_conditions, which never grants a
non-member/non-instructor read access unless the lesson is individually
marked "Include In Preview" on a published course) - nothing here needs
to duplicate that.
"""

import frappe

RESTRICTED_FIELD = "custom_hq_restricted"


def _course_is_restricted(course_name):
    if not course_name:
        return False
    return bool(frappe.db.get_value("LMS Course", course_name, RESTRICTED_FIELD))


def _user_has_lms_course_access(course_name, user=None):
    """
    Same three-way check lms.lms.utils.get_course_details already applies
    to an unpublished course - reused here so a Restricted course behaves
    identically for anyone who'd have been let through that gate anyway.
    """
    from lms.lms.utils import can_modify_course, get_membership

    user = user or frappe.session.user

    if user == "Administrator":
        return True

    if "Moderator" in frappe.get_roles(user):
        return True

    if can_modify_course(course_name):
        return True

    return bool(get_membership(course_name, member=user))


def lms_course_has_permission(doc, ptype="read", user=None):
    """
    LMS Course has_permission hook. Frappe's controller-permission hooks
    can only ever DENY, never grant - has_controller_permissions() takes
    the first falsy return from any registered hook as an immediate
    `{ptype: 0}` and never even reaches the normal role-based permission
    check below it (see frappe/permissions.py). That means this must
    return a real True (not None) for every case that isn't an explicit
    "no", or it would silently deny read access to every LMS Course for
    every user, restricted or not, the instant this hook is registered.
    """
    if ptype not in ("read", "select", "print"):
        return True

    course_name = doc if isinstance(doc, str) else doc.name

    if not _course_is_restricted(course_name):
        return True

    return _user_has_lms_course_access(course_name, user=user)


def lms_course_permission_query_conditions(user=None):
    """
    LMS Course get_permission_query_conditions hook - the list-read
    counterpart of lms_course_has_permission above, EXCEPT deliberately
    stricter: a Restricted course drops out of every course-LISTING query
    (get_courses()/get_featured_home_courses()/get_popular_courses() -
    all plain frappe.get_all("LMS Course", ...) calls, so this applies to
    them automatically) for literally everyone except a true
    Administrator, enrolled or not. "Hidden" means hidden from browsing,
    full stop - an enrolled member still opens it exactly as before (that
    goes through lms_course_has_permission / get_course_details_override
    instead, neither of which this touches), either via a direct link or
    via My Courses (LMS Enrollment-driven, never touches LMS Course as a
    list query at all - unaffected by this).
    """
    user = user or frappe.session.user

    if user == "Administrator":
        return ""

    return f"`tabLMS Course`.{RESTRICTED_FIELD} != 1"


@frappe.whitelist(allow_guest=True)  # matches the original's own allow_guest - guest_access_allowed()
# (checked inside the real function) still governs whether a guest gets past this point at all,
# and _user_has_lms_course_access below never grants a Guest access to a restricted course anyway.
def get_course_details_override(course: str):
    """
    Replaces lms.lms.utils.get_course_details (see
    override_whitelisted_methods in hooks.py) - that function reads the
    course with frappe.db.get_value, which never goes through
    lms_course_has_permission above, and only applies its own "must be a
    member" gate when the course is Unpublished. This applies the same
    gate for a Restricted course too, published or not, then always
    defers to the real function for the actual response - so a course
    that passes never renders any differently than it always has.
    """
    from lms.lms.utils import get_course_details as _original_get_course_details

    if _course_is_restricted(course) and not _user_has_lms_course_access(course):
        return {}

    return _original_get_course_details(course)


@frappe.whitelist(allow_guest=True)
def get_course_outline_override(course: str, progress: bool = False):
    """Same reasoning as get_course_details_override, for the chapter/lesson title list."""
    from lms.lms.utils import get_course_outline as _original_get_course_outline

    if _course_is_restricted(course) and not _user_has_lms_course_access(course):
        return []

    return _original_get_course_outline(course, progress=progress)
