import frappe


def get_franchisor_name():
    return frappe.get_cached_value("User", frappe.session.user, "full_name")
