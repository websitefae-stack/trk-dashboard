import frappe


def get_current_user_roles():
    """Return roles for the current logged-in user."""
    if frappe.session.user == "Guest":
        return []

    return frappe.get_roles(frappe.session.user)


def user_has_role(role):
    """Check whether current user has a specific role."""
    return role in get_current_user_roles()


def require_login():
    """Block guest users from dashboard pages/APIs."""
    if frappe.session.user == "Guest":
        frappe.throw("You must be logged in to access this page.", frappe.PermissionError)


def require_role(role):
    """Require the current user to have a specific role."""
    require_login()

    if not user_has_role(role):
        frappe.throw("You do not have permission to access this page.", frappe.PermissionError)
