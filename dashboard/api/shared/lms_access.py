"""
Two independent settings for a Frappe LMS course, neither of which
touches the course's own Published checkbox - Ashley found the hard way
that unpublishing a course blocks it for EVERYONE, including people
already enrolled in it (lms.lms.utils.get_course_details only checks
membership when the course is unpublished; when published it skips that
check entirely for everyone).

- Show on Website (custom_show_on_website): opt-in, defaults to
  unticked - whether the course appears in the public listing, search
  and category filter at all. A course left unticked still has a real,
  working URL (e.g. for a QR code on physical packaging bundled with a
  course), and still needs the same login/signup as any other course to
  actually access - this only ever controls whether it's found by
  browsing, nothing about who's allowed to open it once found.
- Restricted (custom_hq_restricted): "enrolled/staff only" - blocks
  actually OPENING the course for anyone who isn't enrolled, an
  instructor, or staff, regardless of Show on Website. Applies the same
  "enrolled, instructor/moderator, or nothing" gate LMS itself already
  uses for Course Lesson (see course_lesson.py's own has_permission/
  get_permission_query_conditions in the Learning app - this mirrors
  that pattern for LMS Course, which has neither natively).

What's covered:
- LMS Course's own has_permission/get_permission_query_conditions (this
  file, registered in hooks.py) - blocks a direct document read for a
  Restricted course. Also covers Desk's own LMS Course list view and
  Frappe's global/Awesomebar search (frappe.utils.global_search.search
  checks has_permission per result) - but NOT the public course listing
  itself, see below.
- get_courses / get_course_count / get_course_categories (lms.lms.utils)
  - the public course listing, its pagination count, and the category
  filter dropdown. These call frappe.get_all(), which ALWAYS forces
  ignore_permissions=True regardless of what the caller passes (see
  frappe/__init__.py - it's not "get_list without ignore_permissions",
  it's structurally different) - so permission_query_conditions never
  applied to them at all. Overridden here (see hooks.py's
  override_whitelisted_methods) to require Show on Website (and exclude
  Restricted, as a second safety net) directly, rather than relying on
  a hook that never actually ran against them.
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
SHOW_ON_WEBSITE_FIELD = "custom_show_on_website"


def _course_is_restricted(course_name):
    if not course_name:
        return False
    return bool(frappe.db.get_value("LMS Course", course_name, RESTRICTED_FIELD))


def _is_lms_admin(user=None):
    user = user or frappe.session.user
    return user == "Administrator" or "System Manager" in frappe.get_roles(user)


def _apply_public_listing_visibility(filters):
    """
    Gates what frappe.get_all("LMS Course", ...) actually returns from
    get_courses()/get_course_count() (see their overrides below), and
    who gets which gate:

    - A Desk admin sees everything, same as browsing logged in as
      Administrator/System Manager always has.
    - Anyone else already logged in (a client, coach, franchisee -
      basically anyone with an account) gets ONLY their own enrolled
      courses, full stop, regardless of what filters/tab the LMS
      frontend itself sent. /lms/courses is their own course dashboard,
      not a public catalogue - that's what resilient_domains' own
      trh-courses page is for. Without this, clicking the LMS app's own
      "Courses" breadcrumb (which just requests the generic default
      listing, no "enrolled" tab selected) sent a logged-in client
      straight into the Show on Website gate below and showed them
      nothing, even for courses they're actually enrolled in.
    - An actual Guest gets the real public-listing gate: Show on
      Website required, Restricted excluded.

    filters already asking for "enrolled" or "created" (LMS's own My
    Courses / "courses I teach" tabs - see update_course_filters() in
    lms.lms.utils, which turns either into its own name IN (...) filter
    right after this runs) are left alone either way - already scoped
    to "mine", nothing to add.
    """
    filters = dict(filters or {})

    if filters.get("enrolled") or filters.get("created"):
        return filters

    if _is_lms_admin():
        return filters

    if frappe.session.user != "Guest":
        # Replaces the filters outright rather than adding enrolled=1
        # alongside them - "Live"/"New"/"Upcoming" are about a course's
        # OWN publish timing, meaningless once this is "just show me my
        # own courses" instead, and left in place they still reach
        # update_course_filters() too (e.g. "live" separately sets
        # featured=0 and turns on the featured-courses side-query),
        # untested combinations this never needed to risk. title (the
        # search box) is the one exception worth carrying over - search
        # should still narrow within someone's own courses.
        title = filters.get("title")
        return {"enrolled": 1, "title": title} if title else {"enrolled": 1}

    filters[SHOW_ON_WEBSITE_FIELD] = 1
    filters[RESTRICTED_FIELD] = ["!=", 1]

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
    listing. Injects the Show on Website/Restricted filters (see
    _apply_public_listing_visibility()) before deferring to the real
    function, rather than trying to filter its (paginated,
    featured-courses-mixed-in) return value after the fact.
    """
    from lms.lms.utils import get_courses as _original_get_courses

    filters = _apply_public_listing_visibility(filters)

    return _original_get_courses(filters=filters, start=start, limit_page_length=limit_page_length)


@frappe.whitelist(allow_guest=True)  # nosemgrep
def get_course_count_override(filters: dict = None):
    """Same reasoning as get_courses_override, for the listing page's own pagination count."""
    from lms.lms.utils import get_course_count as _original_get_course_count

    filters = _apply_public_listing_visibility(filters)

    return _original_get_course_count(filters=filters)


@frappe.whitelist(allow_guest=True)  # nosemgrep
def get_course_categories_override():
    """
    Replaces lms.lms.utils.get_course_categories - the category filter
    dropdown on the listing page. The original hardcodes its own
    filters={"published": 1, "category": ["is", "set"]} with no
    parameter to extend them, so this reimplements its one query
    directly (same shape, Show on Website/Restricted added) rather than
    calling through to it - there's nothing else to defer to.

    Deliberately NOT using _apply_public_listing_visibility() here -
    its "logged-in user -> only their enrolled courses" behaviour turns
    into filters["enrolled"] = 1, which only means something to
    get_courses()/get_course_count() (via update_course_filters()
    resolving it into a real name IN (...) condition) - passed straight
    to frappe.get_all() as done here, "enrolled" isn't a real LMS Course
    field at all and would error. The category dropdown stays scoped to
    the public listing regardless of who's logged in - a Desk admin
    still sees every category.
    """
    filters = {"published": 1, "category": ["is", "set"]}

    if not _is_lms_admin():
        filters[SHOW_ON_WEBSITE_FIELD] = 1
        filters[RESTRICTED_FIELD] = ["!=", 1]

    return frappe.get_all(
        "LMS Course",
        filters=filters,
        pluck="category",
        distinct=True,
        order_by="category asc",
        limit_page_length=0,
    )


@frappe.whitelist()
def debug_course_visibility():
    """
    Temporary diagnostic - visit /api/method/dashboard.api.shared.
    lms_access.debug_course_visibility while logged in as whoever is
    seeing no courses on /lms/courses. Shows exactly what this file's
    own logic is doing for that real session, rather than reasoning
    about it from LMS's source code with no way to check it against
    what's actually happening in production. Login required (not
    allow_guest) since the whole point is to see it as a specific,
    already-logged-in person.

    Safe to delete once the actual /lms/courses problem is found - this
    isn't meant to stay.
    """
    from lms.lms.utils import get_courses as _original_get_courses

    user = frappe.session.user

    enrollments = frappe.get_all(
        "LMS Enrollment", filters={"member": user}, fields=["name", "course", "progress"]
    )

    filters_in = {}
    filters_out = _apply_public_listing_visibility(filters_in)

    try:
        courses = _original_get_courses(filters=dict(filters_out), start=0, limit_page_length=20)
        courses_error = None
    except Exception as e:
        courses = None
        courses_error = f"{type(e).__name__}: {e}"

    return {
        "session_user": user,
        "is_lms_admin": _is_lms_admin(),
        "user_roles": frappe.get_roles(user),
        "enrollment_count": len(enrollments),
        "enrollments": enrollments,
        "filters_this_file_would_send_to_get_courses": filters_out,
        "get_courses_result_count": len(courses) if courses is not None else None,
        "get_courses_result": courses,
        "get_courses_error": courses_error,
    }
