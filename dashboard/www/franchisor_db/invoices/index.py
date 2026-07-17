import frappe
from frappe import _

from dashboard.api.shared.permissions import redirect_if_wrong_dashboard
from dashboard.api.shared.invoices import get_invoice_page_data


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    redirect_if_wrong_dashboard("franchisor")

    context.no_cache = 1
    context.page_title = "Invoices"
    context.active_page = "invoices"

    selected_coach = (frappe.form_dict.get("coach") or "").strip()
    data = get_invoice_page_data(dashboard_type="franchisor", selected_coach=selected_coach)

    context.invoices = data.get("invoices", [])
    context.pagination = data.get("pagination", {})
    context.search = data.get("search", "")
    context.from_date = data.get("from_date", "")
    context.to_date = data.get("to_date", "")
    context.status = data.get("status", "Outstanding")
    context.revenue_category = data.get("revenue_category", "")
    context.coach_options = data.get("coach_options", [])
    context.selected_coach = data.get("selected_coach", "")
    context.current_coach = data.get("current_coach", "")
    context.current_coach_label = data.get("current_coach_label", "")
    context.current_company = data.get("current_company", "")
    context.is_franchisor = 1
    context.dashboard_base_path = "/franchisor_db"
