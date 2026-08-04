import frappe
from frappe import _

from dashboard.api.shared.permissions import redirect_if_wrong_dashboard
from dashboard.api.shared.invoices import get_invoice_page_data


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    redirect_if_wrong_dashboard("franchisor")

    context.no_cache = 1
    context.page_title = "Statements"
    context.active_page = "statements"
    context.is_franchisor = 1
    context.dashboard_base_path = "/franchisor_db"

    # Reuses Invoices' own coach-scoping data purely for the coach filter
    # dropdown here - the balances themselves are loaded client-side via
    # get_outstanding_client_balances.
    invoice_context = get_invoice_page_data(dashboard_type="franchisor")
    context.coach_options = invoice_context.get("coach_options", [])
    context.current_coach = invoice_context.get("current_coach", "")
    context.current_coach_label = invoice_context.get("current_coach_label", "")
