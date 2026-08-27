import frappe
from frappe import _

from dashboard.api.shared.permissions import redirect_if_wrong_dashboard
from dashboard.api.shared.coach_view_mode import get_coach_view_mode


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    view_as = frappe.form_dict.get("view_as")
    viewer = frappe.form_dict.get("viewer")

    view_mode = get_coach_view_mode(
        scope=viewer,
        coach_name=view_as,
    )

    if not view_mode.get("is_view_mode"):
        redirect_if_wrong_dashboard("coach")

    requirement_name = (frappe.form_dict.get("name") or "").strip()
    practice_document_name = (frappe.form_dict.get("practice_document") or "").strip()

    if not requirement_name and not practice_document_name:
        frappe.local.flags.redirect_location = "/coach_db/documents"
        raise frappe.Redirect

    # Only used outside view mode - view mode already has its own
    # "return to franchisor" concept (coach_view_return_to below), so
    # this covers the plain "coach viewing their own document" case,
    # where the Back link used to always go to the general Documents
    # list regardless of where the coach actually came from (e.g. the
    # Policies section of their own Onboarding page). Restricted to
    # known internal paths so this can't be used as an open redirect.
    back_to = (frappe.form_dict.get("back_to") or "").strip()
    if not (back_to.startswith("/coach_db/") or back_to.startswith("/franchisor_db/")):
        back_to = "/coach_db/documents"
    context.back_to = back_to

    context.no_cache = 1
    context.page_title = "Document"
    context.active_page = "documents"
    context.dashboard_notifications_url = "/coach_db/notifications" + (view_mode.get("query_string") or "")
    context.requirement_name = requirement_name
    context.practice_document_name = practice_document_name

    context.coach_view_mode = view_mode
    context.coach_view_query = view_mode.get("query_string") or ""
    context.coach_is_view_mode = view_mode.get("is_view_mode") or 0
    context.coach_view_return_to = view_mode.get("return_to") or ""
    context.coach_view_display_name = view_mode.get("view_coach_display_name") or ""

    if context.coach_is_view_mode:
        context.dashboard_user_name = context.coach_view_display_name
    else:
        context.dashboard_user_name = frappe.get_cached_value("User", frappe.session.user, "full_name") or frappe.session.user
