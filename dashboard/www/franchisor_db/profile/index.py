import frappe


def get_context(context):
    context.dashboard_user_name = frappe.get_cached_value("User", frappe.session.user, "full_name")
    context.dashboard_notifications_url = "/franchisor_db/notifications"
