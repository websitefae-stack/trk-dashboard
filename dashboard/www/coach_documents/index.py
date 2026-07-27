import frappe
from frappe import _

from dashboard.api.shared.permissions import ensure_logged_in, get_current_user_dashboard_type

DASHBOARD_HOME = {
	"coach": "/coach_db",
	"franchisor": "/franchisor_db",
	"session_worker": "/session_worker_db",
}


def get_context(context):
	ensure_logged_in()

	dashboard_type = get_current_user_dashboard_type()

	if dashboard_type not in DASHBOARD_HOME:
		frappe.throw(_("You are not allowed to access this page."), frappe.PermissionError)

	context.no_cache = 1
	context.page_title = "My Documents"
	context.active_page = "my_documents"
	context.dashboard_type = dashboard_type
	context.dashboard_home_url = DASHBOARD_HOME[dashboard_type]
	context.dashboard_notifications_url = DASHBOARD_HOME[dashboard_type] + "/notifications"
	context.dashboard_user_name = frappe.get_cached_value("User", frappe.session.user, "full_name") or frappe.session.user
