def get_current_user_dashboard_type():
    if frappe.session.user == "Guest":
        return "guest"

    if is_office_user():
        return "franchisor"

    if _find_session_worker_for_user(frappe.session.user):
        return "session_worker"

    if get_coach_record(frappe.session.user):
        return "coach"

    return "unknown"


def redirect_if_wrong_dashboard(expected):
    current = get_current_user_dashboard_type()

    # 🔒 Block unauthenticated
    if current == "guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    # 🔒 Block unknown users
    if current == "unknown":
        frappe.throw(_("You are not allowed to access this dashboard."), frappe.PermissionError)

    # ✅ Correct dashboard
    if current == expected:
        return

    # 🔁 Redirect to correct dashboard
    redirect_map = {
        "franchisor": "/franchisor_db",
        "coach": "/coach_db",
        "session_worker": "/session_worker_db",
    }

    frappe.local.flags.redirect_location = redirect_map.get(current)
    raise frappe.Redirect
