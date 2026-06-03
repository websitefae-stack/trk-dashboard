import frappe
from frappe import _

from dashboard.api.shared.permissions import redirect_if_wrong_dashboard
from dashboard.api.shared.invoices import get_invoice_page_data
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

    context.no_cache = 1
    context.page_title = "Invoices"
    context.active_page = "invoices"
    context.dashboard_base_path = "/coach_db"

    context.coach_view_mode = view_mode
    context.coach_view_query = view_mode.get("query_string") or ""
    context.coach_is_view_mode = view_mode.get("is_view_mode") or 0
    context.coach_view_return_to = view_mode.get("return_to") or ""
    context.coach_view_display_name = view_mode.get("view_coach_display_name") or ""

    if context.coach_is_view_mode:
        selected_coach = view_mode.get("view_coach_name")
        context.dashboard_user_name = context.coach_view_display_name
    else:
        redirect_if_wrong_dashboard("coach")
        selected_coach = (frappe.form_dict.get("coach") or "").strip()

    data = get_invoice_page_data(
        dashboard_type="coach",
        selected_coach=selected_coach,
    )

    context.invoices = data.get("invoices", [])
    context.coach_options = data.get("coach_options", [])
    context.selected_coach = data.get("selected_coach", "")
    context.current_coach = data.get("current_coach", "")
    context.current_coach_label = data.get("current_coach_label", "")
    context.current_company = data.get("current_company", "")
    context.is_franchisor = 0
