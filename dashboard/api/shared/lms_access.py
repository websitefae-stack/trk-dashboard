"""
Two independent visibility gates for a Frappe LMS course, neither of
which touches the course's own Published checkbox - Ashley found the
hard way that unpublishing a course blocks it for EVERYONE, including
people already enrolled in it (lms.lms.utils.get_course_details only
checks membership when the course is unpublished; when published it
skips that check entirely for everyone).

- Restricted (custom_hq_restricted): "enrolled/staff only" - blocks
  actually OPENING the course for anyone who isn't enrolled, an
  instructor, or staff. Applies the same "enrolled, instructor/
  moderator, or nothing" gate LMS itself already uses for Course Lesson
  (see course_lesson.py's own has_permission/get_permission_query_
  conditions in the Learning app - this mirrors that pattern for LMS
  Course, which has neither natively).
- Unlisted (custom_unlisted): "hidden from browsing, open to anyone
  with the link" - e.g. a course that only ships bundled with a
  physical product, opened via a QR code on the packaging. No
  enrollment or login gate at all - it just never appears in the
  public course listing, search, or category filter.

What's covered:
- LMS Course's own has_permission/get_permission_query_conditions (this
  file, registered in hooks.py) - blocks a direct document read for a
  Restricted course (never Unlisted - that's link-open by design). Also
  covers Desk's own LMS Course list view and Frappe's global/Awesomebar
  search (frappe.utils.global_search.search checks has_permission per
  result) - but NOT the public course listing itself, see below.
- get_courses / get_course_count (lms.lms.utils) - the public course
  listing and its pagination count. These call frappe.get_all(), which
  ALWAYS forces ignore_permissions=True regardless of what the caller
  passes (see frappe/__init__.py - it's not "get_list without
  ignore_permissions", it's structurally different) - so
  permission_query_conditions never applied to them at all, restricted
  or unlisted courses included, and stayed visible on the public browse
  page regardless of either flag. Overridden here (see hooks.py's
  override_whitelisted_methods) to inject a real filter before calling
  through to the originals instead.
- get_course_details (lms.lms.utils) - the course "landing page" data
  fetch, called with frappe.db.get_value directly rather than through
  the permission-checked query layer, so it needs its own override (see
  hooks.py's override_whitelisted_methods) to apply the Restricted gate.
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
UNLISTED_FIELD = "custom_unlisted"


def _course_is_restricted(course_name):
    if not course_name:
        return False
    return bool(frappe.db.get_value("LMS Course", course_name, RESTRICTED_FIELD))


def _is_lms_admin(user=None):
    user = user or frappe.session.user
    return user == "Administrator" or "System Manager" in frappe.get_roles(user)


def _hide_from_public_listing(filters):
    """
    Adds Restricted/Unlisted exclusions directly to a filters dict bound
    for get_courses()/get_course_count() (see their overrides below) -
    both courses stay out of the public listing/search/pagination count
    for anyone but a Desk admin, regardless of which of the two is set.
    """
    filters = dict(filters or {})

    if _is_lms_admin():
        return filters

    filters[RESTRICTED_FIELD] = ["!=", 1]
    filters[UNLISTED_FIELD] = ["!=", 1]

    return filters


def _user_has_lms_course_access(course_name, user=None):
    """
    Same three-way check lms.lms.utils.get_course_details already applies
    to an unpublished course - reused here so a Restricted course behaves
    identically for anyone who'd have been let through that gate anyway.
    Also always lets a Desk admin (System Manager) through - this is a
    website/LMS-facing restriction, never meant to lock Ashley/office out
    of managing the course record itself in Desk. Without this, only the
    literal "Administrator" user and whoever holds the LMS-specific
    Moderator role could even open a Restricted course record at all.
    """
    from lms.lms.utils import can_modify_course, get_membership

    user = user or frappe.session.user

    if user == "Administrator":
        return True

    roles = frappe.get_roles(user)

    if "System Manager" in roles or "Moderator" in roles:
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
    counterpart of lms_course_has_permission above. Covers Desk's own
    LMS Course list view (a permission-checked frappe.get_list query
    same as any other doctype's) and Frappe's Awesomebar/global search
    (frappe.utils.global_search.search checks has_permission per result,
    not this directly, but it's the same "hide it" intent). Does NOT
    cover the actual public course listing on the LMS site itself -
    get_courses()/get_course_count() call frappe.get_all(), which always
    forces ignore_permissions=True no matter what the caller passes, so
    permission_query_conditions never runs against them at all; see
    get_courses_override/get_course_count_override below for how that's
    actually enforced instead.

    System Manager bypasses this the same as Administrator - Desk's own
    LMS Course list view (/app/lms-course) is a list query same as any
    other, so without this a Restricted course would vanish from Ashley's
    own backend list too, not just the public site.
    """
    user = user or frappe.session.user

    if user == "Administrator" or "System Manager" in frappe.get_roles(user):
        return ""

    return f"`tabLMS Course`.{RESTRICTED_FIELD} != 1"


@frappe.whitelist(allow_guest=True)  # matches the original's own allow_guest - guest_access_allowed()
# (checked inside the real function) still governs whether a guest gets past this point at all,
# and _user_has_lms_course_access below never grants a Guest access to a restricted course anyway.
def get_course_details_override(course: str = None):
    """
    Replaces lms.lms.utils.get_course_details (see
    override_whitelisted_methods in hooks.py) - that function reads the
    course with frappe.db.get_value, which never goes through
    lms_course_has_permission above, and only applies its own "must be a
    member" gate when the course is Unpublished. This applies the same
    gate for a Restricted course too, published or not, then always
    defers to the real function for the actual response - so a course
    that passes never renders any differently than it always has.

    course defaults to None (the original has no default at all,
    course: str with nothing after it) because the LMS frontend
    sometimes calls this before it actually has a course id yet - seen
    for real as a Guest hitting a course page and firing this with no
    course in the request at all, which crashed with a TypeError before
    this had a default to fall back on. Same story on
    get_course_outline_override below.
    """
    if not course:
        return {}

    from lms.lms.utils import get_course_details as _original_get_course_details

    if _course_is_restricted(course) and not _user_has_lms_course_access(course):
        return {}

    return _original_get_course_details(course)


@frappe.whitelist(allow_guest=True)
def get_course_outline_override(course: str = None, progress: bool = False):
    """Same reasoning as get_course_details_override, for the chapter/lesson title list."""
    if not course:
        return []

    from lms.lms.utils import get_course_outline as _original_get_course_outline

    if _course_is_restricted(course) and not _user_has_lms_course_access(course):
        return []

    return _original_get_course_outline(course, progress=progress)


@frappe.whitelist(allow_guest=True)  # nosemgrep - matches the originals' own allow_guest
def get_courses_override(filters: dict = None, start: int = 0, limit_page_length=None):
    """
    Replaces lms.lms.utils.get_courses - the actual public course
    listing. Injects the Restricted/Unlisted exclusion into filters (see
    _hide_from_public_listing()) before deferring to the real function,
    rather than trying to filter its (paginated, featured-courses-mixed-
    in) return value after the fact.
    """
    from lms.lms.utils import get_courses as _original_get_courses

    filters = _hide_from_public_listing(filters)

    return _original_get_courses(filters=filters, start=start, limit_page_length=limit_page_length)


@frappe.whitelist(allow_guest=True)  # nosemgrep
def get_course_count_override(filters: dict = None):
    """Same reasoning as get_courses_override, for the listing page's own pagination count."""
    from lms.lms.utils import get_course_count as _original_get_course_count

    filters = _hide_from_public_listing(filters)

    return _original_get_course_count(filters=filters)
