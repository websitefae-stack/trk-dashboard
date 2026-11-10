import frappe
from frappe import _

from dashboard.api.shared.permissions import redirect_if_wrong_dashboard


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.throw(_("Login required"), frappe.PermissionError)

	redirect_if_wrong_dashboard("franchisor")

	request_name = frappe.form_dict.get("name")

	if not request_name:
		frappe.throw(_("Request not found."))

	context.no_cache = 1
	context.page_title = "Safeguarding Assurance Letter"
	context.active_page = "safeguarding_letter_details"
	context.dashboard_user_name = frappe.get_cached_value("User", frappe.session.user, "full_name") or frappe.session.user
	context.request_name = request_name
	context.is_ashley = frappe.session.user == "ashley@theresilientkid.co.uk"
