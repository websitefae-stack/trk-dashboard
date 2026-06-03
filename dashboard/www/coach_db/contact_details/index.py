import frappe
from frappe import _

from dashboard.api.shared.permissions import redirect_if_wrong_dashboard
from dashboard.api.shared.contact_details import get_contact_context
from dashboard.api.shared.contacts import get_current_coach_name
from dashboard.api.shared.coach_view_mode import get_coach_view_mode


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    view_as = frappe.form_dict.get("view_as")
    viewer = frappe.form_dict.get("viewer")

    view_mode = get_coach_view_mode(scope=viewer, coach_name=view_as)

    context.no_cache = 1
    context.active_page = "contacts"
    context.dashboard_notifications_url = "/coach_db/notifications"

    context.coach_view_mode = view_mode
    context.coach_view_query = view_mode.get("query_string") or ""
    context.coach_is_view_mode = view_mode.get("is_view_mode") or 0
    context.coach_view_return_to = view_mode.get("return_to") or ""
    context.coach_view_display_name = view_mode.get("view_coach_display_name") or ""

    if context.coach_is_view_mode:
        context.dashboard_user_name = context.coach_view_display_name
    else:
        redirect_if_wrong_dashboard("coach")
        context.dashboard_user_name = frappe.db.get_value(
            "Coach",
            get_current_coach_name(),
            "coach_name",
        ) or frappe.session.user

    data = get_contact_context(
        scope="coach",
        contact_name=frappe.form_dict.get("name"),
        is_new=False if context.coach_is_view_mode else bool(frappe.form_dict.get("new")),
    )

    context.page_title = data["contact_display_name"]

    for key, value in data.items():
        context[key] = value
