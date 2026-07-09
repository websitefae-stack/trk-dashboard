import frappe
from frappe import _

from dashboard.api.shared.permissions import redirect_if_wrong_dashboard


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    redirect_if_wrong_dashboard("franchisor")

    context.no_cache = 1
    context.active_page = "leads"
    context.dashboard_base_url = "/franchisor_db"

    context.dashboard_user_name = (
        frappe.db.get_value("Coach", {"user": frappe.session.user}, "coach_name")
        or frappe.session.user
    )

    context.is_new = bool(frappe.form_dict.get("new"))
    context.lead_name = frappe.form_dict.get("name") or ""
    context.page_title = "New Lead" if context.is_new else "Lead"
    context.show_coach_field = 1

    context.coaches = frappe.get_all(
        "Coach",
        fields=["name", "coach_name"],
        order_by="coach_name asc",
    )
